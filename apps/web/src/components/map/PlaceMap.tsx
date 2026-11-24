"use client";

import type { LngLatBoundsLike, Map as MapLibre, Marker } from "maplibre-gl";
import { useEffect, useRef, useState } from "react";
import type { Place } from "@/lib/contracts";

const STYLE = process.env.NEXT_PUBLIC_MAP_STYLE || "https://tiles.openfreemap.org/styles/liberty";
const ISAN: LngLatBoundsLike = [[100.8, 14.0], [105.7, 18.5]];
export type Bounds = [west: number, south: number, east: number, north: number];

interface Props {
  places: Place[];
  selected?: string | null;
  onSelect?: (slug: string) => void;
  /** Called after the visitor, not the page, moves the map. */
  onMove?: (bounds: Bounds) => void;
  label: string;
  children?: React.ReactNode;
}

function boundsOf(places: Place[]): LngLatBoundsLike {
  if (!places.length) return ISAN;
  const lons = places.map((p) => p.lon);
  const lats = places.map((p) => p.lat);
  return [[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]];
}

export function PlaceMap({ places, selected = null, onSelect, onMove, label, children }: Props) {
  const box = useRef<HTMLDivElement>(null);
  const markers = useRef<Marker[]>([]);
  const [map, setMap] = useState<MapLibre | null>(null);
  const [failed, setFailed] = useState(false);
  const callbacks = useRef({ onSelect, onMove });
  useEffect(() => {
    callbacks.current = { onSelect, onMove };
  });

  useEffect(() => {
    let disposed = false;
    let created: MapLibre | undefined;
    (async () => {
      try {
        const maplibre = await import("maplibre-gl");
        if (disposed || !box.current) return;
        if (!document.createElement("canvas").getContext("webgl2")) throw new Error("no webgl2");
        maplibre.setWorkerUrl(new URL("/maplibre/maplibre-gl-worker.mjs", location.href).href);
        created = new maplibre.Map({ container: box.current, style: STYLE, bounds: ISAN, attributionControl: { compact: true } });
        created.addControl(new maplibre.NavigationControl({ showCompass: false }), "bottom-right");
        created.on("moveend", (event) => {
          if (!event.originalEvent || !created) return;
          const b = created.getBounds();
          callbacks.current.onMove?.([b.getWest(), b.getSouth(), b.getEast(), b.getNorth()]);
        });
        setMap(created);
      } catch {
        if (!disposed) setFailed(true);
      }
    })();
    return () => {
      disposed = true;
      created?.remove();
      setMap(null);
    };
  }, []);

  useEffect(() => {
    if (!map) return;
    let disposed = false;
    void import("maplibre-gl").then(({ Marker: MapMarker }) => {
      if (disposed) return;
      markers.current = places.map((place) => {
        const pin = document.createElement("button");
        pin.type = "button";
        pin.className = "pin";
        pin.dataset.pin = place.slug;
        pin.setAttribute("aria-label", place.name);
        pin.addEventListener("click", () => callbacks.current.onSelect?.(place.slug));
        return new MapMarker({ element: pin }).setLngLat([place.lon, place.lat]).addTo(map);
      });
      map.fitBounds(boundsOf(places), { padding: 56, maxZoom: 15, animate: false });
    });
    return () => {
      disposed = true;
      markers.current.forEach((m) => m.remove());
      markers.current = [];
    };
  }, [map, places]);

  useEffect(() => {
    for (const marker of markers.current) {
      const pin = marker.getElement();
      pin.setAttribute("aria-pressed", String(pin.dataset.pin === selected));
    }
  }, [selected, places, map]);

  return (
    <div className="map" role="region" aria-label={label}>
      <div className="canvas" ref={box} />
      {failed && <p className="notice">อุปกรณ์นี้แสดงแผนที่ไม่ได้ แต่ยังดูรายชื่อร้านได้ตามปกติ</p>}
      {children}
    </div>
  );
}
