import { startApp } from "./lib/startup.js";

startApp(() => import("./bootstrap.jsx"));
