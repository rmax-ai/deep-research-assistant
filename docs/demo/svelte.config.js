import adapter from "@sveltejs/adapter-static";

const isDev = process.argv.includes("dev");

/** @type {import('@sveltejs/kit').Config} */
export default {
  kit: {
    adapter: adapter({ pages: "build", assets: "build", fallback: "404.html" }),
    paths: {
      base: isDev ? "" : (process.env.BASE_PATH ?? "")
    }
  }
};
