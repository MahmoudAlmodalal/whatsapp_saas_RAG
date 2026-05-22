import type { Metadata } from "next";
import { Tajawal } from "next/font/google";
import "./globals.css";
import QueryProvider from "@/components/QueryProvider";
import { AuthProvider } from "@/components/AuthProvider";

const tajawal = Tajawal({
  subsets: ["arabic"],
  weight: ["300", "400", "500", "700", "800", "900"],
  variable: "--font-tajawal",
});

export const metadata: Metadata = {
  title: "منصة واتساب الذكية | لوحة تحكم الشركاء",
  description: "نظام خدمة العملاء الآلي والمحادثات المباشرة المدعوم بالذكاء الاصطناعي لقطاع الشركات الصغيرة والمتوسطة",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ar" dir="rtl" className="h-full dark">
      <body className={`${tajawal.variable} font-sans bg-slate-950 text-slate-100 h-full antialiased`}>
        <QueryProvider>
          <AuthProvider>
            {children}
          </AuthProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
