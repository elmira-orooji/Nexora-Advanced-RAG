interface Confirmation {
  message: string;
  resolve: (confirmed: boolean) => void;
}
let requests: Confirmation[] = [];
const listeners = new Set<() => void>();
export const confirmationStore = {
  subscribe(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener); }; },
  getSnapshot() { return requests[0] ?? null; },
  answer(confirmed: boolean) {
    const current = requests[0];
    if (!current) return;
    requests = requests.slice(1);
    listeners.forEach((listener) => listener());
    current.resolve(confirmed);
  },
};
export function confirmAction(message: string): Promise<boolean> {
  return new Promise((resolve) => {
    requests = [...requests, { message, resolve }];
    listeners.forEach((listener) => listener());
  });
}
