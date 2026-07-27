/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Vercel автоматически управляет оптимизацией. 
  // output: "standalone" здесь НЕ НУЖЕН и ломает роутинг.
};

export default nextConfig;
