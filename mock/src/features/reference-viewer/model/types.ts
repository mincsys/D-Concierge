export type PdfLocator = {
  page_start: number;
  page_end: number;
};

export type PdfReference = {
  source_type: "pdf";
  label: string;
  url: string;
  locator: PdfLocator;
};

export type DisplayReference = PdfReference;
