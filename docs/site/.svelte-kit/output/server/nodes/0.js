import * as universal from '../entries/pages/_layout.js';

export const index = 0;
let component_cache;
export const component = async () => component_cache ??= (await import('../entries/pages/_layout.svelte.js')).default;
export { universal };
export const universal_id = "src/routes/+layout.js";
export const imports = ["_app/immutable/nodes/0.ljYrTYkJ.js","_app/immutable/chunks/D8X1erAL.js","_app/immutable/chunks/BuXfamnK.js","_app/immutable/chunks/jR7ohOan.js","_app/immutable/chunks/D_FBhXzI.js","_app/immutable/chunks/CZVUbOUz.js","_app/immutable/chunks/a2jkLXE4.js","_app/immutable/chunks/CLD9LV8x.js"];
export const stylesheets = ["_app/immutable/assets/0.CKQcOhcE.css"];
export const fonts = [];
