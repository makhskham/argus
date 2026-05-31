export default function StockPage({ params }: { params: { ticker: string } }) {
  return <div className="p-6"><h1 className="text-xl font-bold text-white">{params.ticker}</h1></div>
}
