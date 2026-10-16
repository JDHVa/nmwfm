import ReactMarkdown from "react-markdown";
import { fileUrl } from "@/lib/api";
import { cn } from "@/lib/utils";

export function Markdown({ texto, className }: { texto: string; className?: string }) {
  return (
    <div
      className={cn(
        "break-words text-sm leading-relaxed [&_a]:text-primary [&_a]:underline [&_code]:rounded [&_code]:bg-muted [&_code]:px-1 [&_code]:py-0.5 [&_code]:text-xs [&_h1]:text-base [&_h1]:font-semibold [&_h2]:text-sm [&_h2]:font-semibold [&_li]:my-0.5 [&_ol]:my-1 [&_ol]:list-decimal [&_ol]:pl-5 [&_p]:my-1 [&_pre]:my-2 [&_pre]:overflow-x-auto [&_pre]:rounded-lg [&_pre]:bg-muted [&_pre]:p-3 [&_ul]:my-1 [&_ul]:list-disc [&_ul]:pl-5",
        className,
      )}
    >
      <ReactMarkdown
        urlTransform={(url) => url}
        components={{
          a: ({ href, children }) => (
            <a
              href={href?.startsWith("/files/") ? fileUrl(href) : href}
              target="_blank"
              rel="noopener noreferrer"
            >
              {children}
            </a>
          ),
        }}
      >
        {texto}
      </ReactMarkdown>
    </div>
  );
}
