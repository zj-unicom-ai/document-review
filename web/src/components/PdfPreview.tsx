// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import { Document, Page, pdfjs } from "react-pdf";
import { useEffect, useRef, useState } from "react";

// pdf.js 渲染线程走本地 worker，不产生外部请求
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url,
).toString();

// 用户要求极简预览：无工具条，固定 80% 缩放
const DEFAULT_SCALE = 0.8;

export function PdfPreview({ blob }: { blob: Blob }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [pageCount, setPageCount] = useState(0);
  const [containerWidth, setContainerWidth] = useState(0);
  const [error, setError] = useState("");

  useEffect(() => {
    const container = containerRef.current;
    // jsdom 等无 ResizeObserver 环境下降级为不自适应宽度
    if (!container || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver((entries) => {
      const width = entries[0]?.contentRect.width ?? 0;
      if (width > 0) setContainerWidth(width);
    });
    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  const pageWidth = Math.max(0, containerWidth - 24);
  const width = pageWidth > 0 ? pageWidth * DEFAULT_SCALE : undefined;

  return (
    <div className="pdf-viewer" ref={containerRef}>
      <div className="pdf-canvas">
        <Document
          file={blob}
          onLoadSuccess={({ numPages }) => {
            setPageCount(numPages);
            setError("");
          }}
          onLoadError={() => setError("批注 PDF 解析失败")}
          loading="批注 PDF 加载中..."
          error={error || "批注 PDF 解析失败"}
        >
          {/* 连续滚动：一次渲染全部页，向下滚动即逐页阅读 */}
          {pageCount > 0
            ? Array.from({ length: pageCount }, (_, index) => (
                <Page
                  key={index + 1}
                  pageNumber={index + 1}
                  width={width}
                  renderTextLayer={false}
                  renderAnnotationLayer={false}
                />
              ))
            : null}
        </Document>
      </div>
    </div>
  );
}
