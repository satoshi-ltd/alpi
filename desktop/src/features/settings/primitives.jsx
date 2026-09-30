import { useLayoutEffect, useRef, useState } from "react";
import Button from "../../primitives/Button.jsx";
import { useNotify } from "../../primitives/Notification.jsx";
import { Section as DSSection, Field as DSField } from "../../primitives/SettingsLayout.jsx";
import { SectionHitProvider, sectionId, settingsMatch, useSectionTitleHit, useSettingsQuery } from "./SettingsNav.jsx";
import { copyText } from "../../lib/clipboard.js";

export function Section({ title, tooltip, kicker, children }) {
  const query = useSettingsQuery();
  const titleHit = !query || settingsMatch(title, query);
  const ref = useRef(null);
  const [noRows, setNoRows] = useState(false);
  useLayoutEffect(() => {
    if (!query || titleHit) {
      setNoRows(false);
      return;
    }
    const rows = ref.current ? Array.from(ref.current.querySelectorAll("[data-settings-row]")) : [];
    setNoRows(!rows.some((r) => !r.hidden));
  }, [query, titleHit, children]);
  return (
    <SectionHitProvider value={!!query && titleHit}>
      <DSSection
        ref={ref}
        id={sectionId(title)}
        label={title}
        kicker={kicker ?? tooltip}
        hidden={!!query && !titleHit && noRows}
      >
        {children}
      </DSSection>
    </SectionHitProvider>
  );
}

export function Row({ label, alignTop, hidden = false, children }) {
  const query = useSettingsQuery();
  const titleHit = useSectionTitleHit();
  const filtered = !!query && !titleHit && !settingsMatch(label, query);
  return (
    <DSField label={label} align={alignTop ? "top" : "center"} hidden={hidden || filtered} searchable>
      {children}
    </DSField>
  );
}

export function CopyButton({ value, message }) {
  const notify = useNotify();
  return (
    <Button
      size="sm"
      onClick={async () => {
        if (await copyText(value)) notify({ message, variant: "success" });
        else notify({ message: "Copy failed", variant: "error" });
      }}
    >
      Copy
    </Button>
  );
}
