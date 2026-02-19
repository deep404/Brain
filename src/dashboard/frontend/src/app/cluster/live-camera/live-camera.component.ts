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
    private processedImg: string | undefined;

    private lastProcessedAtMs: number = 0;
    private processedTtlMs: number = 2500; // > 1 FPS period

    private cameraSubscription: Subscription | undefined;
    private processedSubscription: Subscription | undefined;
    private loadingTimeout: any;
    private refreshTimer: any;

    public overlayMask: string | undefined;
    public overlayVisible: boolean = false;

    private maskSubscription: Subscription | undefined;
    private maskTimeout: any;

    constructor(private webSocketService: WebSocketService) { }

    ngOnInit() {
        this.image = this.createBlackImage();

        // Default stream (serialCamera)
        this.cameraSubscription = this.webSocketService.receiveCamera().subscribe(
            (message) => {
                this.defaultImg = `data:image/jpeg;base64,${message.value}`;
                this.loading = false;

                if (this.loadingTimeout) clearTimeout(this.loadingTimeout);
                this.loadingTimeout = setTimeout(() => {
                    this.loading = true;
                    this.defaultImg = undefined;
                    this.updateDisplayedImage();
                }, 2000);

                this.updateDisplayedImage();
            },
            (error) => {
                this.loading = true;
                this.defaultImg = undefined;
                this.updateDisplayedImage();
                console.error('Error receiving camera:', error);
            }
        );

        this.maskSubscription = this.webSocketService.receiveTrafficSignMask().subscribe(
            (message) => {
                this.overlayMask = `data:image/png;base64,${message.value}`;
                this.overlayVisible = true;

                if (this.maskTimeout) clearTimeout(this.maskTimeout);
                this.maskTimeout = setTimeout(() => {
                    this.overlayVisible = false;   // hide overlay if stale
                }, 1200);
            },
            (error) => {
                this.overlayVisible = false;
            }
        );

        // Processed stream (TrafficSignCamera)
        this.processedSubscription = this.webSocketService.receiveTrafficSignCamera().subscribe(
            (message) => {
                this.processedImg = `data:image/jpeg;base64,${message.value}`;
                this.lastProcessedAtMs = Date.now();
                this.updateDisplayedImage();
            },
            (error) => {
                console.error('Error receiving processed camera:', error);
            }
        );

        // Periodically re-evaluate TTL fallback
        this.refreshTimer = setInterval(() => this.updateDisplayedImage(), 200);
    }

    ngOnDestroy() {
        this.cameraSubscription?.unsubscribe();
        this.processedSubscription?.unsubscribe();

        if (this.maskSubscription) this.maskSubscription.unsubscribe();
        if (this.maskTimeout) clearTimeout(this.maskTimeout);

        if (this.loadingTimeout) clearTimeout(this.loadingTimeout);
        if (this.refreshTimer) clearInterval(this.refreshTimer);

        this.webSocketService.disconnectSocket();
    }

    private updateDisplayedImage() {
        const processedFresh =
            !!this.processedImg && (Date.now() - this.lastProcessedAtMs) < this.processedTtlMs;

        if (processedFresh) {
            this.image = this.processedImg;
            return;
        }

        if (this.defaultImg) {
            this.image = this.defaultImg;
            return;
        }

        this.image = this.createBlackImage();
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
