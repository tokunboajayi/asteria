"use client";

import "cesium/Build/Cesium/Widgets/widgets.css";

import {
  BoundingSphere,
  Cartesian2,
  Cartesian3,
  Cartographic,
  Color,
  ConstantPositionProperty,
  ConstantProperty,
  createWorldTerrainAsync,
  Credit,
  EllipsoidTerrainProvider,
  type Entity,
  HeadingPitchRange,
  HorizontalOrigin,
  ImageryLayer,
  Ion,
  LabelStyle,
  Math as CesiumMath,
  PolylineDashMaterialProperty,
  UrlTemplateImageryProvider,
  VerticalOrigin,
  Viewer,
} from "cesium";
import { useEffect, useRef, useState } from "react";

import type { FlightDetail } from "@/lib/api";
import { fmtM } from "@/lib/format";
import type { Mode } from "@/lib/flightView";
import { modelAt, modelPath, realAt, realTrack, type GeoPoint } from "@/lib/geo";
import { buildRuler, realAltitudeAt, type Ruler } from "@/lib/ruler";

import styles from "./GlobeView.module.css";

const ION_TOKEN = process.env.NEXT_PUBLIC_CESIUM_ION_TOKEN ?? "";

// Imagery without a Cesium ion token: Esri World Imagery (needs no key).
const ESRI_IMAGERY_URL =
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";
const ESRI_ATTRIBUTION = "Esri, Maxar, Earthstar Geographics";

// Same tokens as globals.css: ghost blue, measured white, corrected green, gap amber.
const GHOST = Color.fromCssColorString("#5fb4ff");
const REAL = Color.fromCssColorString("#f5f7fa");
const CORRECTED = Color.fromCssColorString("#3fd18a");
const GAP = Color.fromCssColorString("#ffb020");
const DIM = Color.fromCssColorString("#9aa3af");
const LABEL_BG = Color.fromCssColorString("#05070a").withAlpha(0.82);
const MONO = "500 12px 'IBM Plex Mono', ui-monospace, monospace";
const MONO_SMALL = "400 11px 'IBM Plex Mono', ui-monospace, monospace";

// Map imagery is dimmed so the data, not the farmland, is what the eye lands on.
const IMAGERY_LOOK = { brightness: 0.5, contrast: 1.15, saturation: 0.35 };

declare global {
  interface Window {
    CESIUM_BASE_URL?: string;
  }
}

function cartesians(points: GeoPoint[]): Cartesian3[] {
  return points.map((p) => Cartesian3.fromDegrees(p.lon, p.lat, p.height));
}

interface LatLon {
  lat: number;
  lon: number;
}

interface Markers {
  model: Entity | null;
  modelDrop: Entity | null;
  real: Entity | null;
  realOnRuler: Entity | null;
}

const NO_MARKERS: Markers = { model: null, modelDrop: null, real: null, realOnRuler: null };

interface Props {
  detail: FlightDetail;
  mode: Mode;
  cursor: number;
}

export function Globe({ detail, mode, cursor }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<Viewer | null>(null);
  const markers = useRef<Markers>(NO_MARKERS);
  const rulerSite = useRef<LatLon | null>(null);
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
    styleScene(viewer);
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

  // Paths, ruler and markers: rebuilt when the flight or the mode changes.
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    viewer.entities.removeAll();
    const site = detail.summary.launch_site;
    const elevation = site.elevation_m;
    const corrected = mode === "corrected" && detail.corrected ? detail.corrected : null;
    const modelColor = corrected ? CORRECTED : GHOST;

    const ghostPositions = cartesians(modelPath(detail.ghost, elevation));
    addPath(viewer, "Ghost (physics)", ghostPositions, GHOST, 14);
    addGroundTrack(viewer, ghostPositions, GHOST);
    if (corrected) {
      addPath(viewer, "Corrected (held out)", cartesians(modelPath(corrected, elevation)), CORRECTED, 6);
    }
    const track = realTrack(detail);
    const trackPositions = track && track.length > 1 ? cartesians(track) : [];
    if (trackPositions.length > 0) {
      viewer.entities.add({
        name: "Real (GNSS + logged altitude)",
        polyline: { positions: trackPositions, width: 5, material: REAL.withAlpha(0.15) },
      });
      viewer.entities.add({ polyline: { positions: trackPositions, width: 1.75, material: REAL } });
      addGroundTrack(viewer, trackPositions, REAL);
    }

    // Frame the paths and the ruler's height from a fixed oblique view, far enough to see the whole arc.
    const ruler = buildRuler(detail, mode, fmtM);
    const padTop = Cartesian3.fromDegrees(site.longitude_deg, site.latitude_deg, elevation + ruler.top);
    const sphere = BoundingSphere.fromPoints([...ghostPositions, ...trackPositions, padTop]);
    viewer.camera.flyToBoundingSphere(sphere, {
      duration: 0,
      offset: new HeadingPitchRange(
        CesiumMath.toRadians(-60),
        CesiumMath.toRadians(-10),
        // The panel is wide and short, so its vertical field of view is the narrow one (~30°).
        Math.max(sphere.radius * 3.8, 1500),
      ),
    });
    // The ruler stands just to the camera's right of the pad, so the flight paths never hide it.
    rulerSite.current = beside(viewer, site.latitude_deg, site.longitude_deg, elevation, ruler.top * 0.18);
    addRuler(viewer, ruler, rulerSite.current, elevation);

    markers.current = {
      model: viewer.entities.add({ point: dot(modelColor) }),
      modelDrop: viewer.entities.add({
        polyline: { positions: [], width: 1, material: modelColor.withAlpha(0.45) },
      }),
      real: track ? viewer.entities.add({ point: dot(REAL) }) : null,
      // No position logged: reality is shown as an altitude on the pad ruler, never placed in space.
      realOnRuler: track ? null : viewer.entities.add({ point: dot(REAL) }),
    };

    viewer.scene.requestRender();
  }, [detail, mode]);

  // Cursor markers: moved, never re-created.
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    const site = detail.summary.launch_site;
    const elevation = site.elevation_m;
    const series = mode === "corrected" && detail.corrected ? detail.corrected : detail.ghost;
    const m = markers.current;
    const p = modelAt(series, elevation, cursor);
    place(m.model, p);
    if (m.modelDrop) {
      m.modelDrop.show = p !== null;
      if (p) {
        m.modelDrop.polyline!.positions = new ConstantProperty([
          Cartesian3.fromDegrees(p.lon, p.lat, elevation),
          Cartesian3.fromDegrees(p.lon, p.lat, p.height),
        ]);
      }
    }
    place(m.real, realAt(detail, cursor));
    const realAgl = realAltitudeAt(detail, cursor);
    const at = rulerSite.current;
    place(m.realOnRuler, realAgl === null || !at ? null : { ...at, height: elevation + realAgl });
    viewer.scene.requestRender();
  }, [detail, mode, cursor]);

  if (failure) {
    return (
      <div className={styles.placeholder} role="status">
        3D view unavailable in this browser ({failure}). Everything else works.
      </div>
    );
  }
  return <div ref={container} className={`${styles.globe} ${ION_TOKEN ? "" : styles.noIonLogo}`} />;
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
      : new ImageryLayer(
          new UrlTemplateImageryProvider({
            url: ESRI_IMAGERY_URL,
            // Shown on the map itself, not hidden in the attribution pop-up (Esri's terms).
            credit: new Credit(ESRI_ATTRIBUTION, true),
            maximumLevel: 19,
          }),
        ),
  });
}

/** Night-console look: dimmed, desaturated ground and a darker sky, so the data stands out. */
function styleScene(viewer: Viewer) {
  const layer = viewer.imageryLayers.get(0);
  layer.brightness = IMAGERY_LOOK.brightness;
  layer.contrast = IMAGERY_LOOK.contrast;
  layer.saturation = IMAGERY_LOOK.saturation;
  const scene = viewer.scene;
  scene.globe.depthTestAgainstTerrain = false;
  scene.globe.atmosphereBrightnessShift = -0.35;
  if (scene.skyAtmosphere) {
    scene.skyAtmosphere.brightnessShift = -0.55;
    scene.skyAtmosphere.saturationShift = -0.4;
  }
  scene.backgroundColor = Color.fromCssColorString("#05070a");
}

/** A path drawn twice: a soft halo underneath, the crisp dashed line on top. */
function addPath(viewer: Viewer, name: string, positions: Cartesian3[], color: Color, dash: number) {
  // A tinted halo (a glow material would wash the core to white and lose the colour).
  viewer.entities.add({ polyline: { positions, width: 8, material: color.withAlpha(0.22) } });
  viewer.entities.add({
    name,
    polyline: {
      positions,
      width: 2.5,
      material: new PolylineDashMaterialProperty({ color, dashLength: dash }),
    },
  });
}

/** The path's shadow on the ground, for a sense of drift and depth. */
function addGroundTrack(viewer: Viewer, positions: Cartesian3[], color: Color) {
  viewer.entities.add({
    polyline: { positions, width: 1.5, clampToGround: true, material: color.withAlpha(0.35) },
  });
}

/** The pad ruler: altitude scale above the pad, both apogees and the gap between them. */
function addRuler(viewer: Viewer, ruler: Ruler, site: LatLon, elevation: number) {
  const at = (agl: number) => Cartesian3.fromDegrees(site.lon, site.lat, elevation + agl);
  const modelColor = ruler.modelName === "Corrected" ? CORRECTED : GHOST;
  // Both apogee labels sit right of the ruler, the higher one nudged up and the other down,
  // so they can never overlap each other however small the gap.
  const modelAbove = ruler.model.agl >= ruler.real.agl;

  viewer.entities.add({
    name: "Altitude ruler (above pad)",
    polyline: { positions: [at(0), at(ruler.top)], width: 1.5, material: DIM.withAlpha(0.7) },
  });
  for (const tick of ruler.ticks) {
    viewer.entities.add({
      position: at(tick.agl),
      point: { pixelSize: 4, color: DIM, disableDepthTestDistance: Number.POSITIVE_INFINITY },
      label: tick.label ? label(tick.label, DIM, MONO_SMALL) : undefined,
    });
  }
  // The gap itself: an amber bar between the two apogees.
  viewer.entities.add({
    name: "Apogee gap",
    polyline: { positions: [at(ruler.model.agl), at(ruler.real.agl)], width: 6, material: GAP },
  });
  viewer.entities.add({
    position: at(ruler.model.agl),
    point: { pixelSize: 8, color: modelColor, disableDepthTestDistance: Number.POSITIVE_INFINITY },
    label: label(ruler.model.label, modelColor, MONO, modelAbove ? -10 : 10),
  });
  viewer.entities.add({
    position: at(ruler.real.agl),
    point: { pixelSize: 8, color: REAL, disableDepthTestDistance: Number.POSITIVE_INFINITY },
    label: label(ruler.real.label, REAL, MONO, modelAbove ? 10 : -10),
  });
}

/** The point `metres` to the camera's right of a ground point (the camera has no roll). */
function beside(viewer: Viewer, lat: number, lon: number, elevation: number, metres: number): LatLon {
  const origin = Cartesian3.fromDegrees(lon, lat, elevation);
  const right = Cartesian3.normalize(viewer.camera.rightWC, new Cartesian3());
  const moved = Cartesian3.add(origin, Cartesian3.multiplyByScalar(right, metres, right), new Cartesian3());
  const c = Cartographic.fromCartesian(moved);
  return { lat: CesiumMath.toDegrees(c.latitude), lon: CesiumMath.toDegrees(c.longitude) };
}

/** A label to the right of its point, nudged `dy` pixels vertically. */
function label(text: string, color: Color, font: string, dy = 0) {
  return {
    text,
    font,
    fillColor: color,
    style: LabelStyle.FILL,
    showBackground: true,
    backgroundColor: LABEL_BG,
    backgroundPadding: new Cartesian2(6, 3),
    horizontalOrigin: HorizontalOrigin.LEFT,
    verticalOrigin: VerticalOrigin.CENTER,
    pixelOffset: new Cartesian2(10, dy),
    disableDepthTestDistance: Number.POSITIVE_INFINITY,
  };
}

/** The cursor dot: the blue (or white) dot with a soft halo. */
function dot(color: Color) {
  return {
    pixelSize: 11,
    color,
    outlineColor: color.withAlpha(0.3),
    outlineWidth: 6,
    disableDepthTestDistance: Number.POSITIVE_INFINITY,
  };
}

function place(entity: Entity | null, p: GeoPoint | null) {
  if (!entity) return;
  entity.show = p !== null;
  if (p) entity.position = new ConstantPositionProperty(Cartesian3.fromDegrees(p.lon, p.lat, p.height));
}
