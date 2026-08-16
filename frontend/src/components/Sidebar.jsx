import {
  FileText,
  Map,
  ChevronRight,
} from 'lucide-react';

const Sidebar = ({ activeTab, setActiveTab }) => {
  const menuItems = [
    {
      name: 'Text Analysis',
      icon: FileText,
      description: 'Extract & map places',
    },
    {
      name: 'Map View',
      icon: Map,
      description: 'Explore locations',
    },
  ];

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="brand-icon">G</div>

        <div>
          <h2>GeoMapAI</h2>
          <span>Geospatial Intelligence</span>
        </div>
      </div>

      <div className="sidebar-section-title">
        WORKSPACE
      </div>

      <nav className="sidebar-nav">
        {menuItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.name;

          return (
            <button
              key={item.name}
              className={`sidebar-item ${
                isActive ? 'active' : ''
              }`}
              onClick={() => setActiveTab(item.name)}
            >
              <div className="sidebar-item-icon">
                <Icon size={19} />
              </div>

              <div className="sidebar-item-content">
                <strong>{item.name}</strong>
                <span>{item.description}</span>
              </div>

              {isActive && (
                <ChevronRight
                  size={17}
                  className="sidebar-arrow"
                />
              )}
            </button>
          );
        })}
      </nav>

      <div className="sidebar-footer">
        <div className="status-dot" />

        <div>
          <strong>System Online</strong>
          <span>GeoMapAI Engine</span>
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;