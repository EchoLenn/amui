// Cider's HTTP message bridge cannot POST/DELETE Apple Music favorites itself.
// Use its documented PluginKit event bus and v3 client for this one operation.
const types = new Set(["songs", "library-songs", "music-videos", "library-music-videos"]);
const kinds = {song: "songs", songs: "songs", musicVideo: "music-videos", "music-video": "music-videos", "music-videos": "music-videos"};
let cleanup;

export default {
  identifier: "io.github.echolenn.amui",
  name: "amui Favorites Bridge",
  description: "Explicit favorite changes from the local amui client",
  version: "1.0.0",
  pluginKitVersion: "4",
  author: "EchoLenn",
  repo: "https://github.com/EchoLenn/amui",
  setup() {
    if (cleanup) return;
    const bus = window.__PLUGINSYS__.ExternalMessages;
    const seen = new Set();
    let pending = Promise.resolve();
    let active = true;
    function receive(event) {
      const data = event.detail;
      if (!data || typeof data.id !== "string" || !/^[A-Za-z0-9._:-]{1,128}$/.test(data.id) ||
          !types.has(data.type) || typeof data.state !== "boolean" ||
          typeof data.request !== "string" || !/^[A-Za-z0-9._:-]{1,128}$/.test(data.request) ||
          seen.has(data.request)) return;
      seen.add(data.request);
      if (seen.size > 128) seen.delete(seen.values().next().value);
      const {id: requestedId, type: requestedType, state} = data;
      // Check the current track when each operation begins, not when queued.
      pending = pending.then(async () => {
        if (!active) return;
        const app = window.CiderApp;
        const params = app.RPC.nowPlayingAttributes?.playParams || {};
        const item = app.RPC.nowPlayingMediaItem || {};
        const kind = String(params.kind || item.type || "").replace(/^library-/, "");
        const baseType = kinds[kind];
        const id = String(params.catalogId || params.id || item.id || "");
        const type = id.startsWith("i.") ? `library-${baseType}` : baseType;
        if (id !== requestedId || type !== requestedType) return;
        await app.v3("/v1/me/favorites", {[`ids[${type}]`]: id},
          {paramsInURL: true, fetchOptions: {method: state ? "POST" : "DELETE"}});
      }).catch(() => console.warn("amui: Cider could not apply the favorite change"));
    }
    bus.addEventListener("amui:favorite", receive);
    cleanup = () => {
      active = false;
      bus.removeEventListener("amui:favorite", receive);
      cleanup = undefined;
    };
  },
  teardown() { cleanup?.(); }
};
