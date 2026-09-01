"use client";

import { useRef, useState } from "react";
import {
  Cable,
  FileText,
  Image as ImageIcon,
  Loader2,
  Paperclip,
  Puzzle,
  Video,
  X,
} from "lucide-react";
import type {
  AttachablesResponse,
  ConversationAttachment,
  ConversationAttachmentRef,
} from "@/types";
import { fetchAttachables } from "@/lib/api";
import { cn } from "@/lib/utils";

export type PendingAttachment = {
  localId: string;
  name: string;
  kind: ConversationAttachment["kind"];
  status: "uploading" | "ready" | "error";
  record?: ConversationAttachment;
  ref?: ConversationAttachmentRef;
  error?: string;
};

type AttachmentBarProps = {
  attachments: PendingAttachment[];
  disabled?: boolean;
  onPickFiles: (files: File[], hint: "image" | "video" | "file") => void;
  onPickRef: (ref: ConversationAttachmentRef) => void;
  onRemove: (localId: string) => void;
};

function kindIcon(kind: PendingAttachment["kind"]) {
  switch (kind) {
    case "image":
      return <ImageIcon className="h-3.5 w-3.5" aria-hidden="true" />;
    case "video":
      return <Video className="h-3.5 w-3.5" aria-hidden="true" />;
    case "plugin":
      return <Puzzle className="h-3.5 w-3.5" aria-hidden="true" />;
    case "connection":
      return <Cable className="h-3.5 w-3.5" aria-hidden="true" />;
    default:
      return <FileText className="h-3.5 w-3.5" aria-hidden="true" />;
  }
}

function formatSize(bytes?: number): string {
  if (bytes === undefined) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

/**
 * 输入框附加栏：本地文件 / 图片 / 视频走真实上传；
 * 插件 / 连接以注册表引用方式随消息一起发送。
 */
export function AttachmentBar({
  attachments,
  disabled,
  onPickFiles,
  onPickRef,
  onRemove,
}: AttachmentBarProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [picker, setPicker] = useState<null | "plugin" | "connection">(null);
  const [attachables, setAttachables] = useState<AttachablesResponse | null>(null);
  const [pickerLoading, setPickerLoading] = useState(false);
  const [pickerError, setPickerError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const imageInputRef = useRef<HTMLInputElement>(null);
  const videoInputRef = useRef<HTMLInputElement>(null);

  const openPicker = async (kind: "plugin" | "connection"): Promise<void> => {
    setMenuOpen(false);
    setPicker(kind);
    setPickerError(null);
    if (attachables !== null) return;
    setPickerLoading(true);
    try {
      setAttachables(await fetchAttachables());
    } catch (err) {
      setPickerError(err instanceof Error ? err.message : "无法加载可附加项");
    } finally {
      setPickerLoading(false);
    }
  };

  const handleFiles = (list: FileList | null, hint: "image" | "video" | "file"): void => {
    if (list === null || list.length === 0) return;
    onPickFiles(Array.from(list), hint);
  };

  const menuOptionClass =
    "flex w-full items-center gap-2 rounded-md px-2.5 py-1.5 text-left text-xs text-text-primary hover:bg-surface-hover focus:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring";

  return (
    <div className="relative">
      {/* 待发送附件清单 */}
      {attachments.length > 0 && (
        <ul className="mb-2 flex flex-wrap gap-1.5" aria-label="待发送附件">
          {attachments.map((item) => (
            <li
              key={item.localId}
              className={cn(
                "flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs",
                item.status === "error"
                  ? "border-red-300 bg-red-50 text-red-700"
                  : "border-border-subtle bg-surface-subtle text-text-secondary",
              )}
              title={item.error ?? `${item.name}${item.record?.size !== undefined ? ` · ${formatSize(item.record.size)}` : ""}`}
            >
              {kindIcon(item.kind)}
              <span className="max-w-[10rem] truncate">{item.name}</span>
              {item.status === "uploading" && (
                <Loader2 className="h-3 w-3 animate-spin" aria-label="上传中" />
              )}
              <button
                type="button"
                onClick={() => onRemove(item.localId)}
                className="rounded p-0.5 text-text-tertiary hover:text-text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
                aria-label={`移除 ${item.name}`}
              >
                <X className="h-3 w-3" aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="flex items-center gap-2">
        <input
          ref={fileInputRef}
          type="file"
          multiple
          className="hidden"
          onChange={(e) => {
            handleFiles(e.target.files, "file");
            e.target.value = "";
          }}
        />
        <input
          ref={imageInputRef}
          type="file"
          multiple
          accept="image/*"
          className="hidden"
          onChange={(e) => {
            handleFiles(e.target.files, "image");
            e.target.value = "";
          }}
        />
        <input
          ref={videoInputRef}
          type="file"
          multiple
          accept="video/*"
          className="hidden"
          onChange={(e) => {
            handleFiles(e.target.files, "video");
            e.target.value = "";
          }}
        />

        <button
          type="button"
          disabled={disabled}
          onClick={() => {
            setMenuOpen((open) => !open);
            setPicker(null);
          }}
          className={cn(
            "flex h-9 w-9 items-center justify-center rounded-md border border-border-default text-text-secondary transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring",
            disabled
              ? "cursor-not-allowed opacity-50"
              : "hover:bg-surface-hover hover:text-text-primary",
          )}
          aria-label="添加附件"
          aria-expanded={menuOpen || picker !== null}
          title="添加附件：文件 / 图片 / 视频 / 插件 / 连接"
        >
          <Paperclip className="h-4 w-4" aria-hidden="true" />
        </button>
        <span className="text-xs text-text-tertiary">
          可附加文件、图片、视频、插件、连接
        </span>
      </div>

      {/* 点击外部关闭 */}
      {(menuOpen || picker !== null) && (
        <button
          type="button"
          tabIndex={-1}
          aria-hidden="true"
          className="fixed inset-0 z-10 cursor-default"
          onClick={() => {
            setMenuOpen(false);
            setPicker(null);
          }}
        />
      )}

      {menuOpen && (
        <div className="absolute bottom-11 left-0 z-20 w-44 rounded-lg border border-border-default bg-surface-elevated p-1 shadow-lg">
          <button type="button" className={menuOptionClass} onClick={() => { setMenuOpen(false); fileInputRef.current?.click(); }}>
            <FileText className="h-3.5 w-3.5 text-text-secondary" aria-hidden="true" />
            本地文件
          </button>
          <button type="button" className={menuOptionClass} onClick={() => { setMenuOpen(false); imageInputRef.current?.click(); }}>
            <ImageIcon className="h-3.5 w-3.5 text-text-secondary" aria-hidden="true" />
            图片
          </button>
          <button type="button" className={menuOptionClass} onClick={() => { setMenuOpen(false); videoInputRef.current?.click(); }}>
            <Video className="h-3.5 w-3.5 text-text-secondary" aria-hidden="true" />
            视频
          </button>
          <button type="button" className={menuOptionClass} onClick={() => void openPicker("plugin")}>
            <Puzzle className="h-3.5 w-3.5 text-text-secondary" aria-hidden="true" />
            插件
          </button>
          <button type="button" className={menuOptionClass} onClick={() => void openPicker("connection")}>
            <Cable className="h-3.5 w-3.5 text-text-secondary" aria-hidden="true" />
            连接
          </button>
        </div>
      )}

      {picker !== null && (
        <div className="absolute bottom-11 left-0 z-20 w-72 rounded-lg border border-border-default bg-surface-elevated p-2 shadow-lg">
          <div className="mb-1.5 flex items-center justify-between">
            <span className="text-xs font-medium text-text-primary">
              {picker === "plugin" ? "选择插件" : "选择连接"}
            </span>
            <button
              type="button"
              onClick={() => setPicker(null)}
              className="rounded p-0.5 text-text-tertiary hover:text-text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
              aria-label="关闭选择器"
            >
              <X className="h-3.5 w-3.5" aria-hidden="true" />
            </button>
          </div>
          {pickerLoading && (
            <p className="flex items-center gap-2 py-2 text-xs text-text-secondary">
              <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
              加载中…
            </p>
          )}
          {pickerError && <p className="py-2 text-xs text-red-600">{pickerError}</p>}
          {attachables !== null && (
            <ul className="max-h-48 space-y-0.5 overflow-y-auto">
              {picker === "plugin" &&
                attachables.plugins.map((plugin) => (
                  <li key={plugin.ref_id}>
                    <button
                      type="button"
                      className={menuOptionClass}
                      title={plugin.description}
                      onClick={() => {
                        onPickRef({ kind: "plugin", ref_id: plugin.ref_id, name: plugin.name });
                        setPicker(null);
                      }}
                    >
                      <Puzzle className="h-3.5 w-3.5 shrink-0 text-text-secondary" aria-hidden="true" />
                      <span className="truncate">{plugin.name}</span>
                    </button>
                  </li>
                ))}
              {picker === "connection" &&
                attachables.connections.map((connection) => (
                  <li key={connection.connector_id}>
                    <button
                      type="button"
                      className={menuOptionClass}
                      title={(connection.capabilities ?? []).join(", ")}
                      onClick={() => {
                        onPickRef({
                          kind: "connection",
                          ref_id: connection.connector_id,
                          name: connection.connector_id,
                        });
                        setPicker(null);
                      }}
                    >
                      <Cable className="h-3.5 w-3.5 shrink-0 text-text-secondary" aria-hidden="true" />
                      <span className="truncate">{connection.connector_id}</span>
                      <span className="ml-auto shrink-0 text-[10px] text-text-tertiary">
                        {connection.state ?? ""}
                      </span>
                    </button>
                  </li>
                ))}
              {((picker === "plugin" && attachables.plugins.length === 0) ||
                (picker === "connection" && attachables.connections.length === 0)) && (
                <li className="py-2 text-xs text-text-tertiary">
                  {picker === "plugin" ? "暂无可用插件" : "暂无可用连接"}
                </li>
              )}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
