import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

/**
 * The Vite build of design 11.
 *
 * **The output lands in `STATIC_ROOT`**, which is where WhiteNoise serves
 * it from - on the SAME ORIGIN as the API (design 18.1, CAC-06). One
 * service, one origin, no second host and no CORS.
 *
 * `STATIC_ROOT` is `REPO_ROOT / "staticfiles"` - the repository root's
 * directory, NOT the backend's - so the path here is `../staticfiles`
 * from `frontend/`. The build command of `render.yaml` runs
 * `npm --prefix frontend run build` from the repository root, and the
 * relative path of the build is resolved from `frontend/`, which is
 * where `vite.config.ts` lives.
 *
 * `base: "./"` makes the bundle's own URLs RELATIVE. An absolute
 * `/assets/…` would work on the deployed origin, but a relative one also
 * works when the bundle is served from a sub-path, and it is the form
 * that keeps the bundle from assuming where it lives.
 */
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../staticfiles",
    emptyOutDir: true,
    // The bundle's URL must answer 200 and not a blank page (landmine 2),
    // so the assets are named with a hash and the manifest is written.
    manifest: true,
    rollupOptions: {
      output: {
        entryFileNames: "assets/[name]-[hash].js",
        chunkFileNames: "assets/[name]-[hash].js",
        assetFileNames: "assets/[name]-[hash][extname]",
      },
    },
  },
  base: "./",
});
