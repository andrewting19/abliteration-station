import fs from "node:fs";
import path from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export default function (pi: ExtensionAPI) {
  const root=fs.realpathSync(process.env.ABLITERATION_STATION_TEST_PROJECT!);
  pi.on("tool_call",async event=>{
    if (event.toolName!=="read") return {block:true,reason:"Only fixture reads are permitted in this lifecycle test",terminate:true};
    try {
      const file=fs.realpathSync(path.resolve(root,String(event.input.path)));
      if (file.startsWith(root+path.sep)) return;
    } catch {}
    return {block:true,reason:"Read is outside the isolated test project",terminate:true};
  });
}
