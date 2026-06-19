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
			__memo(() => import('./nodes/1.js')),
			__memo(() => import('./nodes/2.js')),
			__memo(() => import('./nodes/3.js')),
			__memo(() => import('./nodes/4.js')),
			__memo(() => import('./nodes/5.js'))
		],
		remotes: {
			
		},
		routes: [
			{
				id: "/",
				pattern: /^\/$/,
				params: [],
				page: { layouts: [0,], errors: [1,], leaf: 2 },
				endpoint: null
			},
			{
				id: "/api",
				pattern: /^\/api\/?$/,
				params: [],
				page: { layouts: [0,], errors: [1,], leaf: 3 },
				endpoint: null
			},
			{
				id: "/architecture",
				pattern: /^\/architecture\/?$/,
				params: [],
				page: { layouts: [0,], errors: [1,], leaf: 4 },
				endpoint: null
			},
			{
				id: "/phases",
				pattern: /^\/phases\/?$/,
				params: [],
				page: { layouts: [0,], errors: [1,], leaf: 5 },
				endpoint: null
			}
		],
		prerendered_routes: new Set([]),
		matchers: async () => {
			
			return {  };
		},
		server_assets: {}
	}
}
})();
