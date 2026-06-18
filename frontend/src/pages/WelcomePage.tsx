import {
  ArrowRight,
  BarChart3,
  Building2,
  CheckCircle2,
  Compass,
  Database,
  FileDown,
  LandPlot,
  Layers3,
  LogIn,
  MapPinned,
  ShieldCheck,
  Sparkles,
  UserPlus,
  UsersRound,
  LayoutDashboard,
  Map as MapIcon,
  Zap,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { useEffect, useRef } from 'react';
import { motion, useScroll, useTransform, useSpring, useMotionValue, useInView } from 'motion/react';
import './WelcomePage.css';

interface WelcomePageProps {
  onEnterWorkspace?: () => void;
}

const HIGHLIGHTS = [
  {
    icon: Compass,
    title: 'Scenario Exploration',
    description: 'Build and compare planning alternatives in one guided workflow.',
  },
  {
    icon: ShieldCheck,
    title: 'Risk-Aware Decisions',
    description: 'Overlay environmental signals before approving final land-use direction.',
  },
  {
    icon: MapPinned,
    title: 'Parcel-Level Precision',
    description: 'Move from high-level targets to parcel assignments with transparent tradeoffs.',
  },
];

const WORKFLOW_STEPS = [
  {
    icon: Database,
    step: '01',
    title: 'Load planning data',
    description: 'Bring parcel layers, zoning attributes, constraints, and environmental indicators into one workspace.',
  },
  {
    icon: Layers3,
    step: '02',
    title: 'Generate AI scenarios',
    description: 'Create alternative land-use plans using suitability, risk, target mix, and spatial compatibility logic.',
  },
  {
    icon: FileDown,
    step: '03',
    title: 'Compare and export',
    description: 'Review tradeoffs, inspect parcel-level explanations, and export planner-ready decisions.',
  },
];

const VALUE_POINTS = [
  {
    icon: CheckCircle2,
    title: 'Reduce manual planning effort',
    description: 'Automate repetitive scenario preparation while keeping planners in control of decisions.',
  },
  {
    icon: BarChart3,
    title: 'Compare impacts faster',
    description: 'Evaluate risk, land-use mix, spatial conflicts, and optimization scores side by side.',
  },
  {
    icon: LandPlot,
    title: 'Explain parcel decisions',
    description: 'Translate algorithmic assignments into readable planning reasons and warnings.',
  },
];

const AUDIENCES = [
  'Urban Planners',
  'GIS Analysts',
  'Policy Teams',
  'Municipal Decision Makers',
];

// Animated Section Wrapper for scroll-triggered animations
function AnimatedSection({ children, className, delay = 0 }: { children: React.ReactNode; className?: string; delay?: number }) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-100px" });
  
  return (
    <motion.section
      ref={ref}
      initial={{ opacity: 0, y: 60 }}
      animate={isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 60 }}
      transition={{ duration: 0.8, delay, ease: [0.25, 0.1, 0.25, 1] }}
      className={className}
    >
      {children}
    </motion.section>
  );
}

// Mouse-following glow effect
function MouseGlow() {
  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);
  
  const springX = useSpring(mouseX, { stiffness: 50, damping: 20 });
  const springY = useSpring(mouseY, { stiffness: 50, damping: 20 });
  
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      mouseX.set(e.clientX);
      mouseY.set(e.clientY);
    };
    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, [mouseX, mouseY]);
  
  return (
    <motion.div
      className="mouse-glow"
      style={{
        x: springX,
        y: springY,
        translateX: '-50%',
        translateY: '-50%',
      }}
    />
  );
}

export function WelcomePage({ onEnterWorkspace }: WelcomePageProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ container: containerRef });
  const backgroundY = useTransform(scrollYProgress, [0, 1], ['0%', '30%']);
  
  useEffect(() => {
    const originalBodyOverflow = document.body.style.overflow;
    const originalRootOverflow = document.getElementById('root')?.style.overflow;
    const originalHtmlOverflow = document.documentElement.style.overflow;

    document.body.style.overflow = 'auto';
    document.documentElement.style.overflow = 'auto';
    const root = document.getElementById('root');
    if (root) root.style.overflow = 'visible';

    return () => {
      document.body.style.overflow = originalBodyOverflow;
      document.documentElement.style.overflow = originalHtmlOverflow;
      if (root) root.style.overflow = originalRootOverflow || '';
    };
  }, []);
  return (
    <div className="welcome-shell" ref={containerRef}>
      <motion.div className="welcome-grid-overlay" style={{ y: backgroundY }} />
      <div className="welcome-glow welcome-glow-a" />
      <div className="welcome-glow welcome-glow-b" />
      <div className="welcome-glow welcome-glow-c" />
      <MouseGlow />

      <main className="welcome-page">
        <section className="welcome-content" aria-labelledby="welcome-title">
          <motion.article 
            className="welcome-hero-card"
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, ease: [0.25, 0.1, 0.25, 1] }}
          >
            <motion.div 
              className="welcome-pill"
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.5, delay: 0.2 }}
            >
              <Sparkles className="h-3.5 w-3.5" />
              GeoVision Planner
            </motion.div>

            <h1 id="welcome-title" className="welcome-title">
              <motion.span 
                className="typewriter-line typewriter-line-1"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.3 }}
              >
                Welcome to smarter
              </motion.span>
              <motion.span 
                className="typewriter-line typewriter-line-2 welcome-title-accent shimmer-text"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.5 }}
              >
                urban land-use planning
              </motion.span>
            </h1>

            <motion.p 
              className="welcome-description"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.7 }}
            >
              Turn planning goals into clear alternatives, visualize impacts instantly, and produce
              stakeholder-ready outputs with confidence.
            </motion.p>

            <motion.div 
              className="welcome-actions" 
              aria-label="Welcome actions"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.9 }}
            >
              <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.98 }}>
                <Link to="/login" className="welcome-primary-btn pulse-glow">
                  <LogIn className="h-4 w-4" />
                  Sign In
                </Link>
              </motion.div>
              <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.98 }}>
                <Link to="/register" className="welcome-secondary-btn">
                  <UserPlus className="h-4 w-4" />
                  Create Account
                </Link>
              </motion.div>
            </motion.div>

            <motion.p 
              className="welcome-trust-line"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.6, delay: 1.1 }}
            >
              AI-assisted urban planning for faster, explainable, data-backed land-use decisions.
            </motion.p>
          </motion.article>

          {/* Dashboard Preview + Features Stack */}
          <div className="dashboard-stack">
            <motion.div 
              className="dashboard-preview-container"
              initial={{ opacity: 0, x: 60, rotateY: -15 }}
              animate={{ opacity: 1, x: 0, rotateY: 0 }}
              transition={{ duration: 1, delay: 0.6, ease: [0.25, 0.1, 0.25, 1] }}
            >
              <div className="dashboard-preview">
                <div className="dashboard-preview-header">
                  <div className="dashboard-dots">
                    <span></span>
                    <span></span>
                    <span></span>
                  </div>
                  <span className="dashboard-title">GeoVision Dashboard</span>
                </div>
                <div className="dashboard-preview-content">
                  <div className="dashboard-sidebar-mock">
                    <LayoutDashboard className="h-4 w-4" />
                    <MapIcon className="h-4 w-4" />
                    <Zap className="h-4 w-4" />
                  </div>
                  <div className="dashboard-main-mock">
                    <div className="mock-map">
                      <div className="mock-parcel parcel-1"></div>
                      <div className="mock-parcel parcel-2"></div>
                      <div className="mock-parcel parcel-3"></div>
                      <div className="mock-marker"></div>
                    </div>
                    <div className="mock-stats">
                      <div className="mock-stat"></div>
                      <div className="mock-stat"></div>
                      <div className="mock-stat"></div>
                    </div>
                  </div>
                </div>
              </div>
            </motion.div>
            
            {/* Project Features Below Dashboard */}
            <motion.div 
              className="project-features"
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, delay: 1.0 }}
            >
              <div className="feature-row">
                <motion.div 
                  className="feature-badge"
                  whileHover={{ scale: 1.05 }}
                >
                  <Layers3 className="h-4 w-4" />
                  <span>GIS Layers</span>
                </motion.div>
                <motion.div 
                  className="feature-badge"
                  whileHover={{ scale: 1.05 }}
                >
                  <Database className="h-4 w-4" />
                  <span>Parcel Data</span>
                </motion.div>
              </div>
              <div className="feature-row">
                <motion.div 
                  className="feature-badge"
                  whileHover={{ scale: 1.05 }}
                >
                  <BarChart3 className="h-4 w-4" />
                  <span>AI Scenarios</span>
                </motion.div>
                <motion.div 
                  className="feature-badge"
                  whileHover={{ scale: 1.05 }}
                >
                  <FileDown className="h-4 w-4" />
                  <span>Export Plans</span>
                </motion.div>
              </div>
            </motion.div>
          </div>

          <section className="welcome-highlights" aria-label="Product highlights">
            {HIGHLIGHTS.map((item, index) => {
              const Icon = item.icon;
              return (
                <motion.article 
                  key={item.title} 
                  className="welcome-highlight-card"
                  initial={{ opacity: 0, y: 30 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.5, delay: 0.8 + index * 0.15 }}
                  whileHover={{ 
                    y: -6, 
                    boxShadow: '0 20px 40px rgba(79, 255, 167, 0.15)',
                    borderColor: 'rgba(79, 255, 167, 0.4)'
                  }}
                >
                  <motion.div 
                    className="welcome-highlight-icon"
                    whileHover={{ rotate: 5, scale: 1.1 }}
                    transition={{ type: 'spring', stiffness: 400 }}
                  >
                    <Icon className="h-5 w-5" />
                  </motion.div>
                  <h2 className="welcome-highlight-title">{item.title}</h2>
                  <p className="welcome-highlight-description">{item.description}</p>
                </motion.article>
              );
            })}
          </section>
        </section>

        <AnimatedSection id="how-it-works" className="welcome-section welcome-section--workflow" delay={0}>
          <div className="welcome-section-heading">
            <motion.span 
              className="welcome-section-kicker"
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5 }}
            >
              How it works
            </motion.span>
            <motion.h2
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: 0.1 }}
            >
              From GIS data to explainable planning scenarios.
            </motion.h2>
            <motion.p
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: 0.2 }}
            >
              GeoVision keeps the workflow simple for demos and serious enough for planning review.
            </motion.p>
          </div>

          <div className="welcome-workflow-grid">
            {WORKFLOW_STEPS.map((item, index) => {
              const Icon = item.icon;
              const directions = [
                { x: -60, y: 0 },   // Step 1: from left
                { x: 0, y: 60 },    // Step 2: from bottom
                { x: 60, y: 0 }     // Step 3: from right
              ];
              return (
                <motion.article 
                  key={item.step} 
                  className="welcome-workflow-card"
                  initial={{ 
                    opacity: 0, 
                    x: directions[index].x,
                    y: directions[index].y 
                  }}
                  whileInView={{ opacity: 1, x: 0, y: 0 }}
                  viewport={{ once: true, margin: "-50px" }}
                  transition={{ 
                    duration: 0.7, 
                    delay: index * 0.2,
                    ease: [0.25, 0.1, 0.25, 1]
                  }}
                  whileHover={{ 
                    y: -8,
                    boxShadow: '0 24px 48px rgba(79, 255, 167, 0.12)'
                  }}
                >
                  <div className="welcome-workflow-topline">
                    <span>{item.step}</span>
                    <motion.div
                      whileHover={{ rotate: 360, scale: 1.2 }}
                      transition={{ duration: 0.5 }}
                    >
                      <Icon className="h-5 w-5" />
                    </motion.div>
                  </div>
                  <h3>{item.title}</h3>
                  <p>{item.description}</p>
                </motion.article>
              );
            })}
          </div>
        </AnimatedSection>

        <AnimatedSection className="welcome-section welcome-value-layout" delay={0.1}>
          <div className="welcome-section-heading welcome-section-heading--left">
            <motion.span 
              className="welcome-section-kicker"
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5 }}
            >
              Why GeoVision?
            </motion.span>
            <motion.h2
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: 0.1 }}
            >
              Built to make planning decisions easier to compare and defend.
            </motion.h2>
            <motion.p
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: 0.2 }}
            >
              Instead of only displaying GIS layers, GeoVision helps planners move from data to
              scenario generation, impact review, and explainable recommendations.
            </motion.p>
          </div>

          <div className="welcome-value-grid">
            {VALUE_POINTS.map((item, index) => {
              const Icon = item.icon;
              return (
                <motion.article 
                  key={item.title} 
                  className="welcome-value-card"
                  initial={{ opacity: 0, x: 40 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true, margin: "-50px" }}
                  transition={{ 
                    duration: 0.6, 
                    delay: index * 0.15,
                    ease: [0.25, 0.1, 0.25, 1]
                  }}
                  whileHover={{ 
                    x: 8,
                    boxShadow: '0 16px 32px rgba(59, 199, 245, 0.1)'
                  }}
                >
                  <motion.div 
                    className="welcome-value-icon"
                    whileHover={{ scale: 1.15, rotate: 10 }}
                    transition={{ type: 'spring', stiffness: 400 }}
                  >
                    <Icon className="h-5 w-5" />
                  </motion.div>
                  <div>
                    <h3>{item.title}</h3>
                    <p>{item.description}</p>
                  </div>
                </motion.article>
              );
            })}
          </div>
        </AnimatedSection>

        <AnimatedSection className="welcome-section welcome-audience-section" delay={0.1}>
          <motion.div 
            className="welcome-audience-card"
            initial={{ opacity: 0, scale: 0.95 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.7, ease: [0.25, 0.1, 0.25, 1] }}
          >
            <div className="welcome-audience-copy">
              <motion.span 
                className="welcome-section-kicker"
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5 }}
              >
                Built for
              </motion.span>
              <motion.h2
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: 0.1 }}
              >
                Planning teams that need clarity, speed, and accountability.
              </motion.h2>
              <motion.p
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: 0.2 }}
              >
                GeoVision is designed for FYP demos, planning simulations, and GIS-assisted
                decision-support workflows where every recommendation needs a reason.
              </motion.p>
            </div>

            <div className="welcome-audience-list" aria-label="Target users">
              {AUDIENCES.map((audience, index) => (
                <motion.div 
                  key={audience} 
                  className="welcome-audience-pill"
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.4, delay: index * 0.1 }}
                  whileHover={{ 
                    scale: 1.05, 
                    backgroundColor: 'rgba(79, 255, 167, 0.1)',
                    borderColor: 'rgba(79, 255, 167, 0.4)'
                  }}
                >
                  {audience === 'Urban Planners' && <Building2 className="h-4 w-4" />}
                  {audience === 'GIS Analysts' && <MapPinned className="h-4 w-4" />}
                  {audience === 'Policy Teams' && <UsersRound className="h-4 w-4" />}
                  {audience === 'Municipal Decision Makers' && <ShieldCheck className="h-4 w-4" />}
                  <span>{audience}</span>
                </motion.div>
              ))}
            </div>
          </motion.div>
        </AnimatedSection>

        <AnimatedSection className="welcome-final-cta" aria-label="Start using GeoVision" delay={0.1}>
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5 }}
          >
            <span className="welcome-section-kicker">Ready for review</span>
            <h2>Explore the workflow or sign in to open your planning dashboard.</h2>
          </motion.div>
          <motion.div 
            className="welcome-final-actions"
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5, delay: 0.2 }}
          >
            <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.98 }}>
              <Link to="/login" className="welcome-primary-btn cta-glow">
                <span>Open Dashboard</span>
                <motion.span
                  className="arrow-icon"
                  animate={{ x: [0, 5, 0] }}
                  transition={{ duration: 1.5, repeat: Infinity, ease: "easeInOut" }}
                >
                  <ArrowRight className="h-4 w-4" />
                </motion.span>
              </Link>
            </motion.div>
            <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.98 }}>
              <Link to="/register" className="welcome-secondary-btn">
                Create Account
              </Link>
            </motion.div>
          </motion.div>
        </AnimatedSection>
      </main>
    </div>
  );
}
