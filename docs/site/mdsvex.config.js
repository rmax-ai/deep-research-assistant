import { defineMDSveXConfig } from "mdsvex";
import { fileURLToPath } from "url";
import { dirname, resolve } from "path";

const __dirname = dirname(fileURLToPath(import.meta.url));

export default defineMDSveXConfig({
  extensions: [".svx", ".md"],
  smartypants: { dashes: "oldschool" },
  layout: {
    _: resolve(__dirname, "src/lib/DocLayout.svelte"),
  },
});
