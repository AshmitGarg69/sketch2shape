import { useState, useEffect } from "react";
import Hero from "./components/Hero";
import GalleryPage from "./components/gallery/GalleryPage";
import ModernCanvasApplication from "./components/scribble page/modern_canvas_application";
import FinalLoadPage from "./components/final load page/FinalLoadPage";

type Page = "gallery" | "main" | "scribble" | "final";

function getInitialPage(): Page {
  const path = window.location.pathname.toLowerCase();
  if (path === "/main" || path === "/home") return "main";
  if (path === "/scribble" || path === "/draw") return "scribble";
  if (path === "/final" || path === "/load") return "final";
  // The start page is gallery
  return "gallery";
}

function App() {
  const [currentPage, setCurrentPage] = useState<Page>(getInitialPage);

  useEffect(() => {
    const handlePopState = () => {
      setCurrentPage(getInitialPage());
    };
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  const navigateTo = (page: Page) => {
    const targetPath = page === "gallery" ? "/" : `/${page}`;
    if (window.location.pathname !== targetPath) {
      window.history.pushState({ page }, "", targetPath);
    }
    setCurrentPage(page);
    window.scrollTo({ top: 0, behavior: "instant" });
  };

  switch (currentPage) {
    case "gallery":
      return <GalleryPage onNavigateToMain={() => navigateTo("main")} />;

    case "main":
      return (
        <Hero
          onCreateFromScratch={() => navigateTo("scribble")}
          onNavigate={(page) => navigateTo(page as Page)}
        />
      );

    case "scribble":
      return (
        <ModernCanvasApplication
          onGenerate={() => navigateTo("final")}
          onBackToMain={() => navigateTo("main")}
        />
      );

    case "final":
      return <FinalLoadPage onNavigate={(page) => navigateTo(page)} />;

    default:
      return <GalleryPage onNavigateToMain={() => navigateTo("main")} />;
  }
}

export default App;
