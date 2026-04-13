import ScrollingTicker from '../components/landing/ScrollingTicker'
import LandingNav from '../components/landing/LandingNav'
import Hero from '../components/landing/Hero'
import ProductShowcase from '../components/landing/ProductShowcase'
import HowItWorks from '../components/landing/HowItWorks'
import BentoFeatures from '../components/landing/BentoFeatures'
import Stats from '../components/landing/Stats'
import BottomCTA from '../components/landing/BottomCTA'
import Footer from '../components/landing/Footer'

export default function LandingPage() {
  return (
    <div
      className="landing-page"
      style={{
        minHeight: '100vh',
        background: 'var(--bg-primary)',
        color: 'var(--text-primary)',
      }}
    >
      <ScrollingTicker />
      <LandingNav />
      <Hero />
      <ProductShowcase />
      <HowItWorks />
      <BentoFeatures />
      <Stats />
      <BottomCTA />
      <Footer />
    </div>
  )
}
