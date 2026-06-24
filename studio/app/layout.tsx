import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Exam Studio",
  description: "수학 시험지 PDF를 HWPX 문서로 변환하는 AI 워크플로",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>
        <header className="topbar">
          <Link href="/" className="brand">
            📐 Exam Studio
          </Link>
          <nav>
            <Link href="/">파이프라인</Link>
            <Link href="/settings">설정</Link>
          </nav>
        </header>
        <main className="container">{children}</main>
      </body>
    </html>
  );
}
