import { useEffect } from "react";

// Runs reset() when profile-management permission drops (admin→member switch or live demotion) — hiding a surface's entry point doesn't close an already-open modal, which would keep admin-loaded content on screen under a member connection.
export function useCloseAdminSurfacesOnDemotion(allowed, reset) {
  useEffect(() => {
    if (!allowed) reset();
  }, [allowed, reset]);
}
