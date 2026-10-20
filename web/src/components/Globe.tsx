"use client";

import "cesium/Build/Cesium/Widgets/widgets.css";

import {
  BoundingSphere,
  Cartesian3,
  Color,
  ConstantPositionProperty,
  createWorldTerrainAsync,
  EllipsoidTerrainProvider,
  type Entity,
  HeadingPitchRange,
  ImageryLayer,
  Ion,
  Math as CesiumMath,
  OpenStreetMapImageryProvider,
  PolylineDashMaterialProperty,
  Viewer,
} from "cesium";
import { useEffect, useRef, useState } from "react";

import type { FlightDetail } from "@/lib/api";
import type { Mode } from "@/lib/flightView";
import { modelAt, modelPath, realAt, realTrack, type GeoPoint } from "@/lib/geo";

import styles from "./GlobeView.module.css";

const ION_TOKEN = process.env.NEXT_PUBLIC_CESIUM_ION_TOKEN ?? "";

const GHOST = Color.fromCssColorString("#5fb4ff");
const REAL = Color.fromCssColorString("#f5f7fa");
const CORRECTED = Color.fromCssColorString("#3fd18a");

declare global {
  interface Window {
    CESIUM_BASE_URL?: string;
  }
}

function cartesians(points: GeoPoint[]): Cartesian3[] {
  return points.map((p) => Cartesian3.fromDegrees(p.lon, p.lat, p.height));
}

interface Props {
  detail: FlightDetail;
  mode: Mode;
  cursor: number;
}

export function Globe({ detail, mode, cursor }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<Viewer | null>(null);
  const markers = useRef<{ ghost: Entity | null; real: Entity | null }>({ ghost: null, real: null });
  const [failure, setFailure] = useState<string | null>(null);

  // One viewer for the life of the component.
  useEffect(() => {
    if (!container.current) return;
    window.CESIUM_BASE_URL = "/cesium";
    if (ION_TOKEN) Ion.defaultAccessToken = ION_TOKEN;
    let viewer: Viewer;
    try {
      viewer = createViewer(container.current);
    } catch (error) {
      // No WebGL (old GPU, some remote desktops): only the 3D panel degrades, never the console.
      queueMicrotask(() => setFailure(error instanceof Error ? error.message : String(error)));
      return;
    }
    viewer.scene.globe.depthTestAgainstTerrain = false;
    viewerRef.current = viewer;
    if (ION_TOKEN) {
      createWorldTerrainAsync()
        .then((terrain) => {
          if (!viewer.isDestroyed()) {
            viewer.terrainProvider = terrain;
            viewer.scene.requestRender();
          }
        })
        .catch(() => {
          // Keep the smooth ellipsoid if terrain cannot be fetched; nothing else depends on it.
        });
    }
    return () => {
      viewerRef.current = null;
      if (!viewer.isDestroyed()) viewer.destroy();
    };
  }, []);

  // Paths: rebuilt when the flight or the mode changes.
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    viewer.entities.removeAll();
    const elevation = detail.summary.launch_site.elevation_m;
    const ghostPositions = cartesians(modelPath(detail.ghost, elevation));
    viewer.entities.add({
      name: "Ghost (physics)",
      polyline: {
        positions: ghostPositions,
        width: 2,
        material: new PolylineDashMaterialProperty({ color: GHOST, dashLength: 14 }),
      },
    });
    if (mode === "corrected" && detail.corrected) {
      viewer.entities.add({
        name: "Corrected (held out)",
        polyline: {
          positions: cartesians(modelPath(detail.corrected, elevation)),
          width: 2,
          material: new PolylineDashMaterialProperty({ color: CORRECTED, dashLength: 6 }),
        },
      });
    }
    const track = realTrack(detail);
    const trackPositions = track && track.length > 1 ? cartesians(track) : [];
    if (trackPositions.length > 0) {
      viewer.entities.add({
        name: "Real (GNSS + logged altitude)",
        polyline: { positions: trackPositions, width: 2.5, material: REAL },
      });
    }
    const modelColor = mode === "corrected" && detail.corrected ? CORRECTED : GHOST;
    markers.current = {
      ghost: viewer.entities.add({ point: { pixelSize: 9, color: modelColor } }),
      real: track ? viewer.entities.add({ point: { pixelSize: 9, color: REAL } }) : null,
    };
    // Frame every drawn path from a fixed oblique view, far enough to see the whole arc.
    const sphere = BoundingSphere.fromPoints([...ghostPositions, ...trackPositions]);
    viewer.camera.flyToBoundingSphere(sphere, {
      duration: 0,
      offset: new HeadingPitchRange(
        CesiumMath.toRadians(-60),
        CesiumMath.toRadians(-12),
        // The panel is wide and short, so its vertical field of view is the narrow one (~30°).
        Math.max(sphere.radius * 4.5, 1500),
      ),
    });
    viewer.scene.requestRender();
  }, [detail, mode]);

  // Cursor markers: moved, never re-created.
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    const elevation = detail.summary.launch_site.elevation_m;
    const model = mode === "corrected" && detail.corrected ? detail.corrected : detail.ghost;
    place(markers.current.ghost, modelAt(model, elevation, cursor));
    place(markers.current.real, realAt(detail, cursor));
    viewer.scene.requestRender();
  }, [detail, mode, cursor]);

  if (failure) {
    return (
      <div className={styles.placeholder} role="status">
        3D view unavailable in this browser ({failure}). Everything else works.
      </div>
    );
  }
  return <div ref={container} className={styles.globe} />;
}

function createViewer(element: HTMLElement): Viewer {
  return new Viewer(element, {
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
      : new ImageryLayer(new OpenStreetMapImageryProvider({ url: "https://tile.openstreetmap.org/" })),
  });
}

function place(entity: Entity | null, p: GeoPoint | null) {
  if (!entity) return;
  entity.show = p !== null;
  if (p) entity.position = new ConstantPositionProperty(Cartesian3.fromDegrees(p.lon, p.lat, p.height));
}
