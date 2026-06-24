const { createProxyMiddleware } = require("http-proxy-middleware");

module.exports = function setupProxy(app) {
  const apiPort = process.env.FRIDAY_API_PORT || "9001";
  app.use(
    "/api",
    createProxyMiddleware({
      target: `http://127.0.0.1:${apiPort}`,
      changeOrigin: true,
    }),
  );
};
