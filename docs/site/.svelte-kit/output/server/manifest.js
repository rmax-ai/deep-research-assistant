export const manifest = (() => {
function __memo(fn) {
	let value;
	return () => value ??= (value = fn());
}

return {
	appDir: "_app",
	appPath: "_app",
	assets: new Set([".nojekyll"]),
	mimeTypes: {},
	_: {
		client: {start:"_app/immutable/entry/start.B57TuSa_.js",app:"_app/immutable/entry/app.CLxXQb0D.js",imports:["_app/immutable/entry/start.B57TuSa_.js","_app/immutable/chunks/CAjm3wuH.js","_app/immutable/chunks/BuXfamnK.js","_app/immutable/chunks/a2jkLXE4.js","_app/immutable/chunks/CLD9LV8x.js","_app/immutable/entry/app.CLxXQb0D.js","_app/immutable/chunks/BuXfamnK.js","_app/immutable/chunks/CZNSMEbj.js","_app/immutable/chunks/D8X1erAL.js","_app/immutable/chunks/CLD9LV8x.js","_app/immutable/chunks/D_FBhXzI.js","_app/immutable/chunks/BSui46Xm.js"],stylesheets:[],fonts:[],uses_env_dynamic_public:false},
		nodes: [
			__memo(() => import('./nodes/0.js')),
			__memo(() => import('./nodes/1.js'))
		],
		remotes: {
			
		},
		routes: [
			
		],
		prerendered_routes: new Set(["/","/architecture/","/phases/","/api/"]),
		matchers: async () => {
			
			return {  };
		},
		server_assets: {}
	}
}
})();
