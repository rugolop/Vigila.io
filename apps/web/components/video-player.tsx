"use client"

import { useEffect, useRef, useState } from "react"
import videojs from "video.js"
import "video.js/dist/video-js.css"
import type Player from "video.js/dist/types/player"

interface VideoPlayerProps {
  src: string
  type?: string
}

export const VideoPlayer = ({ src, type = "application/x-mpegURL" }: VideoPlayerProps) => {
  const videoRef = useRef<HTMLDivElement>(null)
  const playerRef = useRef<Player | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!videoRef.current) return

    // Reset error state
    setError(null)

    if (!playerRef.current) {
      const videoElement = document.createElement("video-js")
      videoElement.classList.add("vjs-big-play-centered")
      videoRef.current.appendChild(videoElement)

      const player = (playerRef.current = videojs(videoElement, {
        controls: true,
        autoplay: true,
        muted: true, // Muted for autoplay to work
        preload: "auto",
        fluid: false,
        responsive: true,
        aspectRatio: "16:9",
        html5: {
          vhs: {
            overrideNative: true,
          },
          nativeAudioTracks: false,
          nativeVideoTracks: false,
        },
        sources: [
          {
            src,
            type,
          },
        ],
      }))

      // Handle errors
      player.on("error", () => {
        const err = player.error()
        if (err) {
          setError(`Error: ${err.message || "No se pudo cargar el stream"}`)
          console.error("Video.js error:", err)
        }
      })
    } else {
      const player = playerRef.current
      player.src({ src, type })
    }
  }, [src, type])

  useEffect(() => {
    const player = playerRef.current

    return () => {
      if (player && !player.isDisposed()) {
        player.dispose()
        playerRef.current = null
      }
    }
  }, [])

  if (error) {
    return (
      <div className="w-full aspect-video bg-gray-900 flex items-center justify-center rounded">
        <div className="text-center text-gray-400 p-4">
          <p className="text-sm">{error}</p>
          <p className="text-xs mt-2">Verifica que el stream esté disponible</p>
        </div>
      </div>
    )
  }

  return (
    <div data-vjs-player className="w-full">
      <div ref={videoRef} className="vjs-16-9" />
    </div>
  )
}
