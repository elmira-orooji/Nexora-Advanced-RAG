import { Copy } from "lucide-react";
import { useTransientMessage } from "../hooks/useTransientMessage";
export default function CopyTextButton({ value, success, failure, label, className, onError }: {
    value: string;
    success: string;
    failure: string;
    label: string;
    className?: string;
    onError: (message: string) => void;
}) {
    const { message, show } = useTransientMessage();
    const copy = async () => {
        try {
            await navigator.clipboard.writeText(value);
            show(success);
        }
        catch {
            onError(failure);
        }
    };
    return <span className="chat-copy-control"><button type="button" className={className} aria-label={label} title={label} onClick={() => void copy()}><Copy size={14}/></button>{message && <span role="status" className="chat-copy-confirmation">{message}</span>}</span>;
}
