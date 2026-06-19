import "clsx";
function DocLayout($$renderer, $$props) {
  let { children } = $$props;
  $$renderer.push(`<article class="doc svelte-17kmrv">`);
  children($$renderer);
  $$renderer.push(`<!----></article>`);
}
export {
  DocLayout as D
};
