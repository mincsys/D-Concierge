export type PdfReference = {
  title: string;
  description: string;
  url: string;
  pageNumber: number;
};

export const pdfReference: PdfReference = {
  title: "SEC BOOKS 開発指針手引き",
  description: "SEC BOOKS：「つながる世界の開発指針」の実践に向けた手引き PDF p.10",
  url: "/reference-pdf/iot-guide.pdf",
  pageNumber: 10,
};
