import { createContext, useCallback, useContext, useRef, useState } from 'react';

import { ConfirmDialog } from './ConfirmDialog';

const ConfirmContext = createContext(null);

export function ConfirmProvider({ children }) {
  const [request, setRequest] = useState(null);
  const settle = useRef(null);

  const confirm = useCallback(
    (options) =>
      new Promise((resolve) => {
        settle.current?.(false);
        settle.current = resolve;
        setRequest(options);
      }),
    [],
  );

  const close = (answer) => {
    const resolve = settle.current;
    settle.current = null;
    setRequest(null);
    resolve?.(answer);
  };

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      <ConfirmDialog
        open={!!request}
        title={request?.title}
        body={request?.body}
        expected={request?.expected}
        typed={request?.typed ?? request?.expected != null}
        confirmLabel={request?.confirmLabel ?? 'Delete'}
        cancelLabel={request?.cancelLabel ?? 'Cancel'}
        alternateLabel={request?.alternateLabel}
        onAlternate={() => close('alternate')}
        tone={request?.tone ?? 'danger'}
        onConfirm={() => close(true)}
        onClose={() => close(false)}
      />
    </ConfirmContext.Provider>
  );
}

export function useConfirm() {
  return useContext(ConfirmContext) ?? (() => Promise.resolve(false));
}
