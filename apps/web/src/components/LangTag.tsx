// "EN" next to AI-written text served in another language than the page's. The API writes each
// language on its first request and falls back to English when it cannot, so for a while (or for
// good) a headline can be English on a Chinese page; the tag says that is the text, not the page.
import { usePrefs, type Lang } from "../i18n";

export default function LangTag({ lang }: { lang: Lang | null | undefined }) {
  const { prefs, t } = usePrefs();
  if (!lang || lang === prefs.language) return null;
  return (
    <abbr className="lang-tag" title={t("lang.servedIn", { lang: t(`lang.${lang}`) })}>
      {lang.toUpperCase()}
    </abbr>
  );
}
