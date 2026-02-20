import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { Subscription } from 'rxjs';
import { WebSocketService } from '../../webSocket/web-socket.service';

@Component({
  selector: 'app-live-camera',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './live-camera.component.html',
  styleUrl: './live-camera.component.css'
})
export class LiveCameraComponent {
  public image: string | undefined;
  public loading: boolean = true;

  private canvasSize: number[] = [512, 270];
  private defaultImg: string | undefined;

  private cameraSubscription: Subscription | undefined;
  private loadingTimeout: any;

  // Overlays (stacked)
  public trafficSignMask: string | undefined;
  public laneAssistMask: string | undefined;

  private tsMaskSubscription: Subscription | undefined;
  private laneMaskSubscription: Subscription | undefined;

  private tsMaskTimeout: any;
  private laneMaskTimeout: any;

  constructor(private webSocketService: WebSocketService) { }

  ngOnInit() {
    this.image = this.createBlackImage();

    // Always show live serialCamera (smooth FPS)
    this.cameraSubscription = this.webSocketService.receiveCamera().subscribe(
      (message) => {
        this.defaultImg = `data:image/jpeg;base64,${message.value}`;
        this.loading = false;

        if (this.loadingTimeout) clearTimeout(this.loadingTimeout);
        this.loadingTimeout = setTimeout(() => {
          this.loading = true;
          this.defaultImg = undefined;
          this.image = this.createBlackImage();
        }, 2000);

        this.image = this.defaultImg;
      },
      (error) => {
        this.loading = true;
        this.defaultImg = undefined;
        this.image = this.createBlackImage();
        console.error('Error receiving camera:', error);
      }
    );

    // Traffic sign overlay (PNG mask)
    this.tsMaskSubscription = this.webSocketService.receiveTrafficSignMask().subscribe(
      (message) => {
        this.trafficSignMask = `data:image/png;base64,${message.value}`;
        if (this.tsMaskTimeout) clearTimeout(this.tsMaskTimeout);
        this.tsMaskTimeout = setTimeout(() => {
          this.trafficSignMask = undefined;
        }, 1200);
      },
      () => { this.trafficSignMask = undefined; }
    );

    // Lane assist overlay (PNG mask)
    this.laneMaskSubscription = this.webSocketService.receiveLaneAssistMask().subscribe(
      (message) => {
        this.laneAssistMask = `data:image/png;base64,${message.value}`;
        if (this.laneMaskTimeout) clearTimeout(this.laneMaskTimeout);
        this.laneMaskTimeout = setTimeout(() => {
          this.laneAssistMask = undefined;
        }, 1200);
      },
      () => { this.laneAssistMask = undefined; }
    );
  }

  ngOnDestroy() {
    this.cameraSubscription?.unsubscribe();
    this.tsMaskSubscription?.unsubscribe();
    this.laneMaskSubscription?.unsubscribe();
    if (this.tsMaskTimeout) clearTimeout(this.tsMaskTimeout);
    if (this.laneMaskTimeout) clearTimeout(this.laneMaskTimeout);
    if (this.loadingTimeout) clearTimeout(this.loadingTimeout);
  }

  createBlackImage(): string {
    const canvas = document.createElement('canvas');
    canvas.width = this.canvasSize[0];
    canvas.height = this.canvasSize[1];
    const ctx = canvas.getContext('2d');
    if (ctx) {
      ctx.fillStyle = 'black';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
    }
    return canvas.toDataURL('image/png');
  }
}
