// Copyright (c) 2019, Bosch Engineering Center Cluj and BFMC orginazers
// All rights reserved.

// Redistribution and use in source and binary forms, with or without
// modification, are permitted provided that the following conditions are met:

//  1. Redistributions of source code must retain the above copyright notice, this
//    list of conditions and the following disclaimer.

//  2. Redistributions in binary form must reproduce the above copyright notice,
//     this list of conditions and the following disclaimer in the documentation
//     and/or other materials provided with the distribution.

// 3. Neither the name of the copyright holder nor the names of its
//    contributors may be used to endorse or promote products derived from
//     this software without specific prior written permission.

// THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
// AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
// IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
// DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
// FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
// DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
// SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
// CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
// OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
// OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import { Component, Input, ViewChild, ElementRef, AfterViewInit, OnDestroy } from '@angular/core';
import { Subscription } from 'rxjs';
import { WebSocketService } from '../../webSocket/web-socket.service';
import { CommonModule } from '@angular/common';

// ---- Interfaces matching backend data shapes ----

interface GraphNode {
  x: number;
  y: number;
}

interface SignGroup {
  color: string;
  positions: { node: string; x: number; y: number }[];
}

interface GraphData {
  nodes: { [id: string]: GraphNode };
  edges: [string, string][];
  stop_lines: string[];
  roundabout_nodes: string[];
  intersections: number[][];
  signs: { [type: string]: SignGroup };
}

interface RouteData {
  route_coords: number[][];          // raw coordinates (same system as graph nodes)
  stop_lines: { node: string; x: number; y: number; route_idx: number }[];
  signs: { type: string; node: string; x: number; y: number; route_idx: number }[];
  instructions: any[];
}

interface CarPosition {
  x: number;
  y: number;
  route_idx: number;
  total_nodes: number;
}

@Component({
  selector: 'app-map',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './map.component.html',
  styleUrl: './map.component.css'
})
export class MapComponent implements AfterViewInit, OnDestroy {
  @Input() cursorRotation: number = 0;

  @ViewChild('mapCanvas') mapCanvasRef!: ElementRef<HTMLCanvasElement>;
  @ViewChild('mapContainer') mapContainerRef!: ElementRef<HTMLDivElement>;

  public graphLoaded: boolean = false;
  public routeLoaded: boolean = false;
  public carPosition: CarPosition | null = null;

  private graphData: GraphData | null = null;
  private routeData: RouteData | null = null;

  // Bounding box of graph positions (for coordinate mapping)
  private minX = 0; private maxX = 1;
  private minY = 0; private maxY = 1;

  private graphSubscription: Subscription | undefined;
  private routeSubscription: Subscription | undefined;
  private positionSubscription: Subscription | undefined;
  private connectionSubscription: Subscription | undefined;
  private resetSubscription: Subscription | undefined;
  private resizeObserver: ResizeObserver | undefined;

  constructor(private webSocketService: WebSocketService) {}

  ngAfterViewInit() {
    // Subscribe to graph data
    this.graphSubscription = this.webSocketService.receiveMapGraphData().subscribe(
      (data: GraphData) => {
        if (data && data.nodes) {
          this.graphData = data;
          this.graphLoaded = true;
          this.computeBoundingBox();
          this.redraw();
        }
      }
    );

    // Subscribe to route plan data
    this.routeSubscription = this.webSocketService.receiveRoutePlanData().subscribe(
      (data: RouteData) => {
        this.routeData = data;
        this.routeLoaded = true;
        this.redraw();
      }
    );

    // Subscribe to car position updates
    this.positionSubscription = this.webSocketService.receiveCarMapPosition().subscribe(
      (data: CarPosition) => {
        this.carPosition = data;
        this.redraw();
      }
    );

    // Request graph data when connected
    this.connectionSubscription = this.webSocketService.connectionStatus$.subscribe(
      (status) => {
        if (status === 'connected') {
          // Small delay to ensure session is established
          setTimeout(() => {
            this.webSocketService.requestMapGraphData();
          }, 500);
        }
      }
    );

    // Also request immediately if already connected
    if (this.webSocketService.isConnected()) {
      setTimeout(() => {
        this.webSocketService.requestMapGraphData();
      }, 500);
    }

    // Subscribe to dashboard reset (immediate, client-side)
    this.resetSubscription = this.webSocketService.dashboardReset$.subscribe(
      () => {
        this.routeData = null;
        this.routeLoaded = false;
        this.carPosition = null;
        this.redraw();
      }
    );

    // Resize observer to redraw canvas when container resizes
    if (this.mapContainerRef) {
      this.resizeObserver = new ResizeObserver(() => {
        this.redraw();
      });
      this.resizeObserver.observe(this.mapContainerRef.nativeElement);
    }
  }

  ngOnDestroy() {
    this.graphSubscription?.unsubscribe();
    this.routeSubscription?.unsubscribe();
    this.positionSubscription?.unsubscribe();
    this.connectionSubscription?.unsubscribe();
    this.resetSubscription?.unsubscribe();
    this.resizeObserver?.disconnect();
  }

  /** Compute bounding box of all graph node positions. */
  private computeBoundingBox(): void {
    if (!this.graphData) return;

    const nodes = this.graphData.nodes;
    const keys = Object.keys(nodes);
    if (keys.length === 0) return;

    let mnx = Infinity, mxx = -Infinity, mny = Infinity, mxy = -Infinity;
    for (const k of keys) {
      const n = nodes[k];
      if (n.x < mnx) mnx = n.x;
      if (n.x > mxx) mxx = n.x;
      if (n.y < mny) mny = n.y;
      if (n.y > mxy) mxy = n.y;
    }
    this.minX = mnx;
    this.maxX = mxx;
    this.minY = mny;
    this.maxY = mxy;
  }

  /** Full redraw of graph + route + car position. */
  private redraw(): void {
    if (!this.mapCanvasRef || !this.mapContainerRef) return;

    const canvas = this.mapCanvasRef.nativeElement;
    const container = this.mapContainerRef.nativeElement;
    const rect = container.getBoundingClientRect();

    // Set canvas resolution to match container size (high-DPI aware)
    const dpr = window.devicePixelRatio || 1;
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    canvas.style.width = rect.width + 'px';
    canvas.style.height = rect.height + 'px';

    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, rect.width, rect.height);

    if (!this.graphData) return;

    const cw = rect.width;
    const ch = rect.height;

    // Padding to keep nodes away from edges; also maintain aspect ratio
    const dataW = this.maxX - this.minX || 1;
    const dataH = this.maxY - this.minY || 1;
    const dataAspect = dataW / dataH;
    const canvasAspect = cw / ch;

    let pad = 20;
    let effW = cw - 2 * pad;
    let effH = ch - 2 * pad;

    // Adjust padding to maintain aspect ratio
    let offsetX = pad;
    let offsetY = pad;
    if (dataAspect > canvasAspect) {
      // data wider → add vertical padding
      const newH = effW / dataAspect;
      offsetY = pad + (effH - newH) / 2;
      effH = newH;
    } else {
      // data taller → add horizontal padding
      const newW = effH * dataAspect;
      offsetX = pad + (effW - newW) / 2;
      effW = newW;
    }

    // Coordinate mapping functions
    const tx = (x: number): number => offsetX + ((x - this.minX) / dataW) * effW;
    // Mirror-reverse by OX axis: flip y so top↔bottom
    const ty = (y: number): number => offsetY + ((this.maxY - y) / dataH) * effH;

    const nodes = this.graphData.nodes;
    const stopSet = new Set(this.graphData.stop_lines);

    // ===== 1. Draw edges (thin grey lines) =====
    ctx.save();
    ctx.strokeStyle = 'rgba(100, 110, 130, 0.35)';
    ctx.lineWidth = 0.6;
    for (const [u, v] of this.graphData.edges) {
      const nu = nodes[u];
      const nv = nodes[v];
      if (!nu || !nv) continue;
      ctx.beginPath();
      ctx.moveTo(tx(nu.x), ty(nu.y));
      ctx.lineTo(tx(nv.x), ty(nv.y));
      ctx.stroke();
    }
    ctx.restore();

    // ===== 2. Draw all nodes (small dots) =====
    ctx.save();
    const nodeR = Math.max(1.5, Math.min(3, cw / 300));
    for (const [id, node] of Object.entries(nodes)) {
      const cx = tx(node.x);
      const cy = ty(node.y);
      ctx.beginPath();
      ctx.arc(cx, cy, nodeR, 0, 2 * Math.PI);
      if (stopSet.has(id)) {
        ctx.fillStyle = 'rgba(225, 87, 89, 0.9)'; // red for stop lines
      } else {
        ctx.fillStyle = 'rgba(130, 140, 160, 0.8)'; // grey for normal
      }
      ctx.fill();
    }
    ctx.restore();

    // ===== 3. Draw node IDs (optional, only at large zoom) =====
    const showLabels = effW > 500;
    if (showLabels) {
      ctx.save();
      const fontSize = Math.max(6, Math.min(10, effW / 100));
      ctx.font = `${fontSize}px Arial`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'bottom';
      for (const [id, node] of Object.entries(nodes)) {
        const cx = tx(node.x);
        const cy = ty(node.y);
        ctx.fillStyle = stopSet.has(id) ? 'rgba(225, 87, 89, 0.8)' : 'rgba(180, 190, 200, 0.6)';
        ctx.fillText(id, cx, cy - nodeR - 1);
      }
      ctx.restore();
    }

    // ===== 4. Draw sign bubbles =====
    if (this.graphData.signs) {
      ctx.save();
      const signR = Math.max(3, Math.min(6, cw / 200));
      for (const [signType, group] of Object.entries(this.graphData.signs)) {
        const color = group.color || '#ffffff';
        for (const pos of group.positions) {
          const cx = tx(pos.x);
          const cy = ty(pos.y);
          ctx.beginPath();
          ctx.arc(cx, cy, signR, 0, 2 * Math.PI);
          ctx.fillStyle = color;
          ctx.fill();
          ctx.strokeStyle = 'rgba(0,0,0,0.4)';
          ctx.lineWidth = 0.8;
          ctx.stroke();
        }
      }
      ctx.restore();
    }

    // ===== 5. Draw route (crimson line with arrows) =====
    if (this.routeData && this.routeData.route_coords.length > 1) {
      const coords = this.routeData.route_coords;

      // Glow underneath
      ctx.save();
      ctx.strokeStyle = 'rgba(220, 20, 60, 0.25)';
      ctx.lineWidth = 5;
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      ctx.beginPath();
      ctx.moveTo(tx(coords[0][0]), ty(coords[0][1]));
      for (let i = 1; i < coords.length; i++) {
        ctx.lineTo(tx(coords[i][0]), ty(coords[i][1]));
      }
      ctx.stroke();

      // Bright crimson line
      ctx.strokeStyle = 'rgba(220, 20, 60, 0.9)';
      ctx.lineWidth = 2.2;
      ctx.beginPath();
      ctx.moveTo(tx(coords[0][0]), ty(coords[0][1]));
      for (let i = 1; i < coords.length; i++) {
        ctx.lineTo(tx(coords[i][0]), ty(coords[i][1]));
      }
      ctx.stroke();
      ctx.restore();

      // Direction arrows along the route (every ~30 nodes)
      const arrowStep = Math.max(20, Math.floor(coords.length / 25));
      ctx.save();
      ctx.fillStyle = 'rgba(220, 20, 60, 0.85)';
      for (let i = arrowStep; i < coords.length; i += arrowStep) {
        const x1 = tx(coords[i - 1][0]), y1 = ty(coords[i - 1][1]);
        const x2 = tx(coords[i][0]), y2 = ty(coords[i][1]);
        const dx = x2 - x1, dy = y2 - y1;
        const len = Math.hypot(dx, dy);
        if (len < 1) continue;
        const ux = dx / len, uy = dy / len;
        const size = 5;
        ctx.beginPath();
        ctx.moveTo(x2, y2);
        ctx.lineTo(x2 - size * ux + size * 0.5 * uy, y2 - size * uy - size * 0.5 * ux);
        ctx.lineTo(x2 - size * ux - size * 0.5 * uy, y2 - size * uy + size * 0.5 * ux);
        ctx.closePath();
        ctx.fill();
      }
      ctx.restore();

      // Stop lines on route (highlighted red dots)
      if (this.routeData.stop_lines) {
        ctx.save();
        for (const sl of this.routeData.stop_lines) {
          const cx = tx(sl.x);
          const cy = ty(sl.y);
          ctx.beginPath();
          ctx.arc(cx, cy, 4, 0, 2 * Math.PI);
          ctx.fillStyle = 'rgba(255, 50, 50, 0.9)';
          ctx.fill();
          ctx.strokeStyle = '#fff';
          ctx.lineWidth = 1;
          ctx.stroke();
        }
        ctx.restore();
      }

      // Start marker (green)
      ctx.save();
      ctx.beginPath();
      ctx.arc(tx(coords[0][0]), ty(coords[0][1]), 7, 0, 2 * Math.PI);
      ctx.fillStyle = '#44ff44';
      ctx.fill();
      ctx.strokeStyle = '#000';
      ctx.lineWidth = 2;
      ctx.stroke();
      ctx.restore();

      // End marker (blue)
      const last = coords[coords.length - 1];
      ctx.save();
      ctx.beginPath();
      ctx.arc(tx(last[0]), ty(last[1]), 7, 0, 2 * Math.PI);
      ctx.fillStyle = '#44aaff';
      ctx.fill();
      ctx.strokeStyle = '#000';
      ctx.lineWidth = 2;
      ctx.stroke();
      ctx.restore();
    }

    // ===== 6. Draw car position =====
    if (this.carPosition) {
      const cx = tx(this.carPosition.x);
      const cy = ty(this.carPosition.y);

      ctx.save();
      ctx.shadowColor = '#ffdd00';
      ctx.shadowBlur = 14;
      ctx.beginPath();
      ctx.arc(cx, cy, 9, 0, 2 * Math.PI);
      ctx.fillStyle = '#ffdd00';
      ctx.fill();
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 2;
      ctx.stroke();

      ctx.shadowBlur = 0;
      ctx.beginPath();
      ctx.arc(cx, cy, 4, 0, 2 * Math.PI);
      ctx.fillStyle = '#ff4400';
      ctx.fill();
      ctx.restore();

      // Progress %
      if (this.carPosition.total_nodes > 0) {
        const pct = Math.round((this.carPosition.route_idx / this.carPosition.total_nodes) * 100);
        ctx.save();
        ctx.font = 'bold 11px Arial';
        ctx.fillStyle = '#ffffff';
        ctx.textAlign = 'center';
        ctx.fillText(`${pct}%`, cx, cy - 15);
        ctx.restore();
      }
    }
  }
}
