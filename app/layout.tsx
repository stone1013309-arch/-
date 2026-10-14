import { Analytics } from '@vercel/analytics/next'
import type { Metadata, Viewport } from 'next'
import { Geist, Geist_Mono } from 'next/font/google'
import './globals.css'

const geistSans = Geist({
  subsets: ['latin'],
  variable: '--font-geist-sans',
})

const geistMono = Geist_Mono({
  subsets: ['latin'],
  variable: '--font-geist-mono',
})

export const metadata: Metadata = {
  title: '訓練日曆 · 健身紀錄',
  description: '每天記錄腿 / 拉 / 推訓練與照片，自動判斷今天該練什麼',
  generator: 'v0.app',
  manifest: '/manifest.json',
}

export const viewport: Viewport = {
  userScalable: false,
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
}

// App 版不需要 Service Worker 與 Vercel Analytics
const isApp = process.env.NEXT_PUBLIC_BUILD_TARGET === 'app'

const swScript = `if('serviceWorker' in navigator){window.addEventListener('load',function(){navigator.serviceWorker.register('/sw.js').catch(function(){})})}`

const themeScript = `(function(){try{var t=localStorage.getItem('fitness-theme');if(t==='dark'){document.documentElement.classList.add('dark');document.documentElement.style.colorScheme='dark';}else{document.documentElement.style.colorScheme='light';}}catch(e){}})();`

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html
      lang="zh-Hant"
      suppressHydrationWarning
      className={`bg-background ${geistSans.variable} ${geistMono.variable}`}
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
        {process.env.NODE_ENV === 'production' && !isApp && (
          <script dangerouslySetInnerHTML={{ __html: swScript }} />
        )}
      </head>
      <body className="font-sans antialiased">
        {children}
        {process.env.NODE_ENV === 'production' && !isApp && <Analytics />}
      </body>
    </html>
  )
}
