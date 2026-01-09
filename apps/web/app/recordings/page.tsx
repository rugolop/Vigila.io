import { RecordingsGallery } from "@/components/recordings-gallery"
import { Metadata } from "next"

export const metadata: Metadata = {
  title: "Recordings",
  description: "View and manage your camera recordings",
}

export default function RecordingsPage() {
  return (
    <div className="min-h-screen p-8">
      <main className="max-w-7xl mx-auto">
        <h1 className="text-3xl font-bold mb-8">Recordings</h1>
        <RecordingsGallery />
      </main>
    </div>
  )
}
