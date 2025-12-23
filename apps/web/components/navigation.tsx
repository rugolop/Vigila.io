"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"

export const Navigation = () => {
  const pathname = usePathname()

  const navItems = [
    { name: "Live View", href: "/" },
    { name: "Recordings", href: "/recordings" },
    { name: "Settings", href: "/settings" },
  ]

  return (
    <nav className="bg-gray-800 text-white shadow-md">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center">
            <h1 className="text-xl font-bold">Smart DVR</h1>
          </div>
          <div className="flex space-x-4">
            {navItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  pathname === item.href
                    ? "bg-gray-900 text-white"
                    : "text-gray-300 hover:bg-gray-700 hover:text-white"
                }`}
              >
                {item.name}
              </Link>
            ))}
          </div>
        </div>
      </div>
    </nav>
  )
}
