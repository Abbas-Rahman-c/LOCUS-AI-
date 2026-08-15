import { useState } from 'react'
import { LocusLogo } from './LocusLogo'
import { useNavigate } from 'react-router-dom'
import { TermsAndConditionsModal } from './TermsAndConditionsModal'

export function Header() {
  const navigate = useNavigate()
  const [showTermsModal, setShowTermsModal] = useState(false)

  const handleLoginClick = () => {
    setShowTermsModal(true)
  }

  const handleTermsClose = () => {
    setShowTermsModal(false)
  }

  const handleTermsAgree = () => {
    setShowTermsModal(false)
    navigate('/welcome')
  }

  return (
    <>
      <header className="flex items-center justify-between px-8 pt-6 pb-2 lg:px-10">
        <LocusLogo />

        <div className="flex items-center gap-8">
          <nav className="hidden items-center gap-8 sm:flex">
            <a
              href="#how-it-works"
              className="text-[14px] font-medium text-[#6b7280] transition-colors hover:text-[#111827]"
            >
              How it works
            </a>
            <a
              href="#why-locus"
              className="text-[14px] font-medium text-[#6b7280] transition-colors hover:text-[#111827]"
            >
              Why Locus AI
            </a>
          </nav>

          <button
            type="button"
            onClick={handleLoginClick}
            className="rounded-full border border-[#d1d5db] bg-white px-5 py-1.5 text-[14px] font-medium text-[#374151] transition-colors hover:bg-gray-50"
          >
            Log in
          </button>
        </div>
      </header>

      <TermsAndConditionsModal
        isOpen={showTermsModal}
        onClose={handleTermsClose}
        onAgree={handleTermsAgree}
      />
    </>
  )
}
