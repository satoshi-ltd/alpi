import { useNow } from "../hooks/useNow.js";
import { relativeTime } from "../lib/time.js";

export default function RelativeTime({ ts }) {
  const now = useNow();
  return relativeTime(ts, now);
}
