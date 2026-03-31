export type TemplateLink = {
  label: string;
  href: string;
};

export function buildTemplateLinks(templateBase: string, endpoint: string): TemplateLink[] {
  const baseUrl = `${templateBase}/${endpoint}`;
  return [
    { label: "Download Example", href: `${baseUrl}?type=example` },
    { label: "Download Empty File", href: `${baseUrl}?type=empty` },
  ];
}
