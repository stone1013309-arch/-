// BUILD_TARGET=app：給 Capacitor 打包用的純靜態網站（輸出到 out/）
// 靜態網站不能有伺服器 API，所以只收 .tsx 頁面，把 app/api/**/route.ts 排除在外；
// App 裡的 AI 判斷改呼叫 NEXT_PUBLIC_API_BASE 指定的線上網站
const isApp = process.env.BUILD_TARGET === 'app'

/** @type {import('next').NextConfig} */
const nextConfig = {
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
  env: {
    NEXT_PUBLIC_BUILD_TARGET: isApp ? 'app' : 'web',
  },
  ...(isApp && {
    output: 'export',
    pageExtensions: ['tsx'],
  }),
}

export default nextConfig
