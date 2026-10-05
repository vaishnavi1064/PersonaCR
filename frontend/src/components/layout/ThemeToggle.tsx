import { Sun, Moon } from 'lucide-react'
import { useStore } from '../../store/useStore'
import IconButton from '../ui/IconButton'

export default function ThemeToggle() {
  const { theme, toggleTheme } = useStore()

  const handleClick = () => {
    toggleTheme()
    const next = theme === 'dark' ? 'light' : 'dark'
    document.documentElement.setAttribute('data-theme', next)
  }

  return (
    <IconButton
      onClick={handleClick}
      label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
      variant="outline"
      icon={theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}
    />
  )
}
