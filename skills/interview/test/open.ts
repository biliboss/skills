// Calls the launcher once, as the queue server does (tests): node test/open.ts <queue url>
import { openWindow } from "../launch.ts";

await openWindow(process.argv[2], {}, false);
