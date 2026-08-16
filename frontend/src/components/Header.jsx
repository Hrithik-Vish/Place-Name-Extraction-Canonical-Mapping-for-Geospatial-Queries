import {
  Moon,
  Sun,
  Sparkles,
} from 'lucide-react';

const Header = ({ theme, toggleTheme }) => {
  const handleThemeToggle = () => {
    const button = document.querySelector('.theme-button');

    if (!button) {
      toggleTheme();
      return;
    }

    const rect = button.getBoundingClientRect();

    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;

    const maxX = Math.max(centerX, window.innerWidth - centerX);
    const maxY = Math.max(centerY, window.innerHeight - centerY);

    const radius = Math.sqrt(
      maxX * maxX + maxY * maxY
    );

    document.documentElement.style.setProperty(
      '--theme-x',
      `${centerX}px`
    );

    document.documentElement.style.setProperty(
      '--theme-y',
      `${centerY}px`
    );

    document.documentElement.style.setProperty(
      '--theme-radius',
      `${radius}px`
    );

    document.documentElement.classList.add(
      'theme-transitioning'
    );

    toggleTheme();

    window.setTimeout(() => {
      document.documentElement.classList.remove(
        'theme-transitioning'
      );
    }, 750);
  };

  return (
    <header className="top-header">
      <div className="header-title">
        <div className="header-title-main">
          <Sparkles size={16} />

          <h1>Analysis Workspace</h1>
        </div>

        <p>
          Place-name extraction & canonical mapping
        </p>
      </div>

      <div className="header-actions">
        <div className="system-status">
          <span className="live-dot" />
          System Online
        </div>

        <button
          type="button"
          className="theme-button"
          onClick={handleThemeToggle}
          aria-label={
            theme === 'dark'
              ? 'Switch to light mode'
              : 'Switch to dark mode'
          }
          title={
            theme === 'dark'
              ? 'Switch to light mode'
              : 'Switch to dark mode'
          }
        >
          <span className="theme-icon">
            {theme === 'dark' ? (
              <Sun size={18} />
            ) : (
              <Moon size={18} />
            )}
          </span>
        </button>
      </div>
    </header>
  );
};

export default Header;