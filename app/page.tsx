export default function HomePage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="bg-white p-8 rounded-2xl shadow-2xl max-w-md w-full text-center">
        <h1 className="text-3xl font-bold text-gray-800 mb-4">
          ✅ Vercel работает!
        </h1>
        <p className="text-gray-600 mb-6">
          Роутинг исправен. Проблема была в коде page.tsx
        </p>
        <button className="bg-blue-500 hover:bg-blue-600 text-white font-bold py-2 px-4 rounded">
          Тестовая кнопка
        </button>
      </div>
    </div>
  );
}
