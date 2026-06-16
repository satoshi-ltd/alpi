import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import ImageLightbox from "./ImageLightbox.jsx";
import styles from "./ProducedImages.module.css";

const MIME = {
  png: "image/png", jpg: "image/jpeg", jpeg: "image/jpeg",
  webp: "image/webp", gif: "image/gif",
};

function Tile({ image, onZoom }) {
  const [src, setSrc] = useState(null);
  useEffect(() => {
    let alive = true;
    setSrc(null);
    const mime = MIME[image.path.toLowerCase().split(".").pop()];
    if (!mime) return undefined;
    const dir = image.path.replace(/[/\\][^/\\]*$/, "");
    invoke("attachment_thumb", { path: image.path, mime, roots: dir ? [dir] : [] })
      .then((url) => { if (alive) setSrc(url || null); })
      .catch(() => { if (alive) setSrc(null); });
    return () => { alive = false; };
  }, [image.path]);

  if (!src) {
    return (
      <div className={styles.tile}>
        <span className={styles.fallback}>{image.name}</span>
      </div>
    );
  }
  return (
    <button
      type="button"
      className={styles.tile}
      onClick={() => onZoom({ src, path: image.path, caption: image.name })}
    >
      <img className={styles.img} src={src} alt={image.name || ""} />
    </button>
  );
}

export default function ProducedImages({ images }) {
  const [zoom, setZoom] = useState(null);
  if (!images?.length) return null;
  return (
    <div className={images.length > 1 ? styles.grid : styles.single}>
      {images.map((im) => (
        <Tile key={im.path} image={im} onZoom={setZoom} />
      ))}
      {zoom && (
        <ImageLightbox
          src={zoom.src}
          path={zoom.path}
          caption={zoom.caption}
          onClose={() => setZoom(null)}
        />
      )}
    </div>
  );
}
