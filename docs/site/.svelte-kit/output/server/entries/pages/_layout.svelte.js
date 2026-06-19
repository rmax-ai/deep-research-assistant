import { h as head, a as attr } from "../../chunks/index.js";
import { b as base } from "../../chunks/server.js";
import "../../chunks/url.js";
import "@sveltejs/kit/internal/server";
import "../../chunks/root.js";
function _layout($$renderer, $$props) {
  let { children } = $$props;
  head("12qhfyh", $$renderer, ($$renderer2) => {
    $$renderer2.push(`<link rel="preconnect" href="https://fonts.googleapis.com"/> <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin=""/> <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&amp;family=Inter:wght@400;500;600;700;800&amp;display=swap" rel="stylesheet"/>`);
  });
  $$renderer.push(`<div class="app svelte-12qhfyh"><nav class="top-nav svelte-12qhfyh"><a${attr("href", base + "/")} class="logo svelte-12qhfyh">Deep Research</a> <div class="nav-links svelte-12qhfyh"><a${attr("href", base + "/architecture/")} class="svelte-12qhfyh">Architecture</a> <a${attr("href", base + "/phases/")} class="svelte-12qhfyh">Phases</a> <a${attr("href", base + "/api/")} class="svelte-12qhfyh">API</a> <a href="https://github.com/rmax-ai/deep-research-assistant" class="gh-link svelte-12qhfyh">GitHub ↗</a></div></nav> <main class="svelte-12qhfyh">`);
  children($$renderer);
  $$renderer.push(`<!----></main> <footer class="svelte-12qhfyh"><p>Deep Research Assistant · MIT License · Built with ADK 2.0 + SvelteKit</p></footer></div>`);
}
export {
  _layout as default
};
