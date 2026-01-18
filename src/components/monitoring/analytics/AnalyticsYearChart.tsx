import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

interface AnalyticsYearChartProps {
  analytics: {
    by_year: { year: number; count: number }[];
    by_year_section: { year: number; section: string; count: number }[];
    by_section: { section: string; count: number }[];
  };
}

const AnalyticsYearChart = ({ analytics }: AnalyticsYearChartProps) => {
  const [selectedSectionFilter, setSelectedSectionFilter] = useState<string>('all');

  const getYearChartData = () => {
    if (!analytics) return [];
    
    if (selectedSectionFilter === 'all') {
      return analytics.by_year;
    }
    
    return analytics.by_year_section
      .filter(item => item.section === selectedSectionFilter)
      .map(item => ({ year: item.year, count: item.count }));
  };

  const yearChartData = getYearChartData();
  const totalInYearChart = yearChartData.reduce((sum, item) => sum + item.count, 0);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Документы по годам</CardTitle>
            <CardDescription>Количество документов по годам публикации</CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-600">Всего: <span className="font-bold text-gray-900">{totalInYearChart}</span></span>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap gap-2 mb-4">
          <Button 
            variant={selectedSectionFilter === 'all' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setSelectedSectionFilter('all')}
          >
            Все разделы
          </Button>
          {analytics.by_section.map((section) => (
            <Button 
              key={section.section}
              variant={selectedSectionFilter === section.section ? 'default' : 'outline'}
              size="sm"
              onClick={() => setSelectedSectionFilter(section.section)}
            >
              {section.section}
            </Button>
          ))}
        </div>

        <ResponsiveContainer width="100%" height={400}>
          <BarChart data={yearChartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis 
              dataKey="year" 
              tick={{ fontSize: 12 }}
            />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip 
              contentStyle={{ 
                backgroundColor: 'white', 
                border: '1px solid #e5e7eb',
                borderRadius: '8px'
              }}
            />
            <Bar 
              dataKey="count" 
              fill="#10b981"
              radius={[8, 8, 0, 0]}
            />
          </BarChart>
        </ResponsiveContainer>

        <div className="mt-6 grid grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-3">
          {yearChartData.map((item) => (
            <div key={item.year} className="p-3 border rounded-lg text-center hover:bg-gray-50 transition-colors">
              <div className="text-xs text-gray-500">{item.year}</div>
              <div className="text-lg font-bold text-gray-900 mt-1">{item.count}</div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
};

export default AnalyticsYearChart;
