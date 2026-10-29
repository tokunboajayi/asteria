"use client";

import "cesium/Build/Cesium/Widgets/widgets.css";

import {
  BoundingSphere,
  Cartesian2,
  Cartesian3,
  Color,
  ConstantPositionProperty,
  ConstantProperty,
  createWorldTerrainAsync,
  Credit,
  EllipsoidTerrainProvider,
  type Entity,
  HeadingPitchRange,
  ImageryLayer,
  Ion,
  LabelStyle,
  Math as CesiumMath,
  Matrix4,
  PolylineDashMaterialProperty,
  UrlTemplateImageryProvider,
  Viewer,
} from "cesium";
import { useEffect, useRef, useState } from "react";

import type { GapSeries, GeoPoint, ObjectEphemeris } from "@/lib/api";

import styles from "./GlobeView.module.css";

const ION_TOKEN = process.env.NEXT_PUBLIC_CESIUM_ION_TOKEN ?? "";

const ESRI_IMAGERY_URL =
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";
const ESRI_ATTRIBUTION = "Esri, Maxar, Earthstar Geographics";

const GHOST = Color.fromCssColorString("#5fb4ff");
const REAL = Color.fromCssColorString("#f5f7fa");
const GAP = Color.fromCssColorString("#ffb020");
const LABEL_BG = Color.fromCssColorString("#05070a").withAlpha(0.85);
const MONO = "600 12px 'IBM Plex Mono', ui-monospace, monospace";
const MONO_SMALL = "400 11px 'IBM Plex Mono', ui-monospace, monospace";

const IMAGERY_LOOK = { brightness: 0.5, contrast: 1.15, saturation: 0.35 };

function toCartesian(p: GeoPoint): Cartesian3 {
  return Cartesian3.fromDegrees(p.lon, p.lat, p.alt_km * 1000.0);
}

function groundCartesian(p: GeoPoint): Cartesian3 {
  return Cartesian3.fromDegrees(p.lon, p.lat, 0.0);
}

/** The series' sampled ghost and tracked positions (real SGP4 states, one per tracked epoch). */
export function seriesPoints(s: GapSeries): { ghost: GeoPoint[]; tracked: GeoPoint[] } {
  return {
    ghost: s.epochs.map((_, i) => ({ lat: s.ghost_lat[i], lon: s.ghost_lon[i], alt_km: s.ghost_alt_km[i] })),
    tracked: s.epochs.map((_, i) => ({
      lat: s.tracked_lat[i],
      lon: s.tracked_lon[i],
      alt_km: s.tracked_alt_km[i],
    })),
  };
}

export type CameraMode = "overview" | "satellite" | "gap";

interface Props {
  name: string;
  series: GapSeries;
  ephemeris: ObjectEphemeris;
  epochIndex: number;
  errorScale: number;
  cameraMode: CameraMode;
}

export function OrbitGlobe({ name, series, ephemeris, epochIndex, errorScale, cameraMode }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<Viewer | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  // Dynamic entities
  const ghostMarker = useRef<Entity | null>(null);
  const trackedMarker = useRef<Entity | null>(null);
  const gapLine = useRef<Entity | null>(null);
  // Overview flies once per object or mode change, not on every scrub.
  const lastOverview = useRef<string | null>(null);

  useEffect(() => {
    if (!container.current) return;
    window.CESIUM_BASE_URL = "/cesium";
    if (ION_TOKEN) Ion.defaultAccessToken = ION_TOKEN;
    let viewer: Viewer;
    try {
      viewer = new Viewer(container.current, {
        animation: false,
        timeline: false,
        baseLayerPicker: false,
        geocoder: false,
        homeButton: false,
        sceneModePicker: false,
        navigationHelpButton: false,
        fullscreenButton: false,
        infoBox: false,
        selectionIndicator: false,
        requestRenderMode: true,
        terrainProvider: new EllipsoidTerrainProvider(),
        baseLayer: ION_TOKEN
          ? ImageryLayer.fromWorldImagery({})
          : new ImageryLayer(
              new UrlTemplateImageryProvider({
                url: ESRI_IMAGERY_URL,
                credit: new Credit(ESRI_ATTRIBUTION, true),
                maximumLevel: 19,
              }),
            ),
      });
    } catch (error) {
      queueMicrotask(() => setFailure(error instanceof Error ? error.message : String(error)));
      return;
    }

    const layer = viewer.imageryLayers.get(0);
    layer.brightness = IMAGERY_LOOK.brightness;
    layer.contrast = IMAGERY_LOOK.contrast;
    layer.saturation = IMAGERY_LOOK.saturation;
    viewer.scene.globe.depthTestAgainstTerrain = false;
    viewer.scene.globe.atmosphereBrightnessShift = -0.35;
    if (viewer.scene.skyAtmosphere) {
      viewer.scene.skyAtmosphere.brightnessShift = -0.55;
      viewer.scene.skyAtmosphere.saturationShift = -0.4;
    }
    viewer.scene.backgroundColor = Color.fromCssColorString("#05070a");
    viewerRef.current = viewer;

    if (ION_TOKEN) {
      createWorldTerrainAsync()
        .then((terrain) => {
          if (!viewer.isDestroyed()) {
            viewer.terrainProvider = terrain;
            viewer.scene.requestRender();
          }
        })
        .catch(() => {});
    }

    return () => {
      viewerRef.current = null;
      if (!viewer.isDestroyed()) viewer.destroy();
    };
  }, []);

  // Static orbital paths & revolution loop
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    viewer.entities.removeAll();

    // One revolution of each orbit from the last tracked epoch: ghost (dashed) and tracked.
    const addArc = (points: GeoPoint[], color: Color, dashed: boolean, label: string) => {
      if (points.length < 2) return;
      viewer.entities.add({
        name: label,
        polyline: {
          positions: points.map(toCartesian),
          width: dashed ? 2.5 : 2,
          material: dashed
            ? new PolylineDashMaterialProperty({ color: color.withAlpha(0.7), dashLength: 16.0 })
            : color.withAlpha(0.6),
        },
      });
      viewer.entities.add({
        polyline: {
          positions: points.map(groundCartesian),
          width: 1,
          clampToGround: true,
          material: color.withAlpha(0.2),
        },
      });
    };
    addArc(ephemeris.ghost_arc, GHOST, true, "Ghost orbit, one revolution");
    addArc(ephemeris.tracked_arc, REAL, false, "Tracked orbit, one revolution");

    // Create markers for dynamic updates
    ghostMarker.current = viewer.entities.add({
      point: {
        pixelSize: 10,
        color: GHOST,
        outlineColor: GHOST.withAlpha(0.35),
        outlineWidth: 6,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
      label: {
        text: "GHOST",
        font: MONO_SMALL,
        fillColor: GHOST,
        style: LabelStyle.FILL,
        showBackground: true,
        backgroundColor: LABEL_BG,
        backgroundPadding: new Cartesian2(6, 3),
        pixelOffset: new Cartesian2(12, -8),
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
    });

    trackedMarker.current = viewer.entities.add({
      point: {
        pixelSize: 12,
        color: REAL,
        outlineColor: REAL.withAlpha(0.4),
        outlineWidth: 8,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
      label: {
        text: "TRACKED",
        font: MONO,
        fillColor: REAL,
        style: LabelStyle.FILL,
        showBackground: true,
        backgroundColor: LABEL_BG,
        backgroundPadding: new Cartesian2(6, 3),
        pixelOffset: new Cartesian2(14, 10),
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
    });

    gapLine.current = viewer.entities.add({
      name: "Gap, tracked − ghost",
      polyline: {
        positions: [],
        width: 4,
        material: GAP,
      },
    });

    viewer.scene.requestRender();
  }, [name, ephemeris]);

  // Position updates on epoch or error scale changes
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;

    const pts = seriesPoints(series);
    const k = Math.min(Math.max(0, epochIndex), series.epochs.length - 1);
    if (k < 0) return;
    const gCart = toCartesian(pts.ghost[k]);
    const tCart = toCartesian(pts.tracked[k]);

    // Apply error exaggeration scale if > 1
    let effectiveTracked = tCart;
    if (errorScale > 1) {
      const diff = Cartesian3.subtract(tCart, gCart, new Cartesian3());
      const scaledDiff = Cartesian3.multiplyByScalar(diff, errorScale, new Cartesian3());
      effectiveTracked = Cartesian3.add(gCart, scaledDiff, new Cartesian3());
    }

    if (ghostMarker.current) {
      ghostMarker.current.position = new ConstantPositionProperty(gCart);
    }
    if (trackedMarker.current) {
      trackedMarker.current.position = new ConstantPositionProperty(effectiveTracked);
    }

    if (gapLine.current && gapLine.current.polyline) {
      gapLine.current.polyline.positions = new ConstantProperty([gCart, effectiveTracked]);
    }

    // Camera: lookAt locks the camera to a point, so release it before flying elsewhere.
    viewer.camera.lookAtTransform(Matrix4.IDENTITY);
    const overviewKey = `${name}:${series.base_epoch}`;
    if (cameraMode !== "overview") lastOverview.current = null;
    if (cameraMode === "overview" && lastOverview.current !== overviewKey) {
      lastOverview.current = overviewKey;
      const sphere = new BoundingSphere(Cartesian3.ZERO, 6378137 + series.base_mean_altitude_km * 1000 + 4000000);
      viewer.camera.flyToBoundingSphere(sphere, {
        duration: 0.5,
        offset: new HeadingPitchRange(0, CesiumMath.toRadians(-35), sphere.radius * 2.8),
      });
    } else if (cameraMode === "satellite") {
      viewer.camera.lookAt(
        effectiveTracked,
        new HeadingPitchRange(
          CesiumMath.toRadians(45),
          CesiumMath.toRadians(-25),
          Math.max(1200000, series.base_mean_altitude_km * 1800),
        ),
      );
    } else if (cameraMode === "gap") {
      const mid = Cartesian3.midpoint(gCart, effectiveTracked, new Cartesian3());
      const dist = Cartesian3.distance(gCart, effectiveTracked);
      viewer.camera.lookAt(
        mid,
        new HeadingPitchRange(0, CesiumMath.toRadians(-30), Math.max(dist * 3.5, 400000)),
      );
    }

    viewer.scene.requestRender();
  }, [name, series, epochIndex, errorScale, cameraMode]);

  if (failure) {
    return (
      <div className={styles.placeholder} role="status">
        3D view unavailable in this browser ({failure}).
      </div>
    );
  }

  return <div ref={container} className={`${styles.globe} ${ION_TOKEN ? "" : styles.noIonLogo}`} />;
}
