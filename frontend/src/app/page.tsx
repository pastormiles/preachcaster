import Link from "next/link";

export default function Home() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-orange-50 to-white">
      {/* Header */}
      <header className="py-6 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto flex justify-between items-center">
          <h1 className="text-2xl font-bold text-orange-600">PreachCaster</h1>
          <div className="space-x-4">
            <Link
              href="/auth/login"
              className="text-gray-600 hover:text-gray-900"
            >
              Sign in
            </Link>
            <Link
              href="/auth/register"
              className="px-4 py-2 bg-orange-600 text-white rounded-md hover:bg-orange-700"
            >
              Get Started
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <div className="text-center">
          <h2 className="text-4xl sm:text-5xl font-bold text-gray-900 mb-6">
            Turn Your YouTube Sermons
            <br />
            Into a Podcast
          </h2>
          <p className="text-xl text-gray-600 max-w-2xl mx-auto mb-8">
            Connect your church&apos;s YouTube channel and automatically create a
            podcast. Distributed to Apple Podcasts, Spotify, and everywhere people listen.
          </p>
          <Link
            href="/auth/register"
            className="inline-block px-8 py-3 bg-orange-600 text-white text-lg font-medium rounded-md hover:bg-orange-700"
          >
            Start Free Trial
          </Link>
        </div>

        {/* Features */}
        <div className="mt-24 grid md:grid-cols-3 gap-8">
          <div className="text-center p-6">
            <div className="w-12 h-12 bg-orange-100 text-orange-600 rounded-full flex items-center justify-center mx-auto mb-4 text-2xl">
              1
            </div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">
              Connect YouTube
            </h3>
            <p className="text-gray-600">
              Link your church&apos;s YouTube channel with one click
            </p>
          </div>

          <div className="text-center p-6">
            <div className="w-12 h-12 bg-orange-100 text-orange-600 rounded-full flex items-center justify-center mx-auto mb-4 text-2xl">
              2
            </div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">
              Automatic Conversion
            </h3>
            <p className="text-gray-600">
              We extract audio, transcripts, and metadata automatically
            </p>
          </div>

          <div className="text-center p-6">
            <div className="w-12 h-12 bg-orange-100 text-orange-600 rounded-full flex items-center justify-center mx-auto mb-4 text-2xl">
              3
            </div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">
              Podcast Published
            </h3>
            <p className="text-gray-600">
              Your RSS feed works with Apple Podcasts, Spotify, and more
            </p>
          </div>
        </div>

        {/* Benefits */}
        <div className="mt-24 bg-white rounded-2xl shadow-lg p-8 md:p-12">
          <h3 className="text-2xl font-bold text-gray-900 mb-8 text-center">
            Everything Your Church Needs
          </h3>
          <div className="grid md:grid-cols-2 gap-6">
            <div className="flex items-start space-x-3">
              <span className="text-blue-500 text-xl">&#10003;</span>
              <div>
                <p className="font-medium text-gray-900">Automatic audio extraction</p>
                <p className="text-gray-600 text-sm">High-quality MP3 from every video</p>
              </div>
            </div>
            <div className="flex items-start space-x-3">
              <span className="text-blue-500 text-xl">&#10003;</span>
              <div>
                <p className="font-medium text-gray-900">Timestamped transcripts</p>
                <p className="text-gray-600 text-sm">Click any line to jump to that moment</p>
              </div>
            </div>
            <div className="flex items-start space-x-3">
              <span className="text-blue-500 text-xl">&#10003;</span>
              <div>
                <p className="font-medium text-gray-900">RSS feed for podcatchers</p>
                <p className="text-gray-600 text-sm">Apple Podcasts, Spotify, Google Podcasts</p>
              </div>
            </div>
            <div className="flex items-start space-x-3">
              <span className="text-blue-500 text-xl">&#10003;</span>
              <div>
                <p className="font-medium text-gray-900">Public sermon pages</p>
                <p className="text-gray-600 text-sm">Shareable links with audio player</p>
              </div>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="py-8 text-center text-gray-500 text-sm">
        &copy; 2026 PreachCaster. A product of Nomion AI.
      </footer>
    </div>
  );
}
