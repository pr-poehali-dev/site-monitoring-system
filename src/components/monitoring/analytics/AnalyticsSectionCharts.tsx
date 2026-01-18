import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';

interface AnalyticsSectionChartsProps {
  analytics: {
    by_section: { section: string; count: number }[];
    total_documents: number;
  };
}

const COLORS = {
  'Постановления': '#3b82f6',
  'Распоряжения': '#10b981', 
  'Муниципальные программы': '#f59e0b'
};

const PIE_COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'];

const AnalyticsSectionCharts = ({ analytics }: AnalyticsSectionChartsProps) => {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <Card>
        <CardHeader>
          <CardTitle>Документы по разделам</CardTitle>
          <CardDescription>Количество документов в каждом разделе</CardDescription>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={analytics.by_section}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis 
                dataKey="section" 
                tick={{ fontSize: 12 }}
                angle={-15}
                textAnchor="end"
                height={80}
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
                fill="#3b82f6"
                radius={[8, 8, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>

          <div className="mt-6 space-y-3">
            {analytics.by_section.map((item) => (
              <div key={item.section} className="flex items-center justify-between p-3 border rounded-lg">
                <div className="flex items-center gap-3">
                  <div 
                    className="w-3 h-3 rounded-full" 
                    style={{ backgroundColor: COLORS[item.section as keyof typeof COLORS] || '#94a3b8' }}
                  />
                  <span className="text-sm font-medium text-gray-900">{item.section}</span>
                </div>
                <Badge variant="secondary">{item.count} док.</Badge>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Соотношение разделов</CardTitle>
          <CardDescription>Процентное распределение документов</CardDescription>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={analytics.by_section}
                dataKey="count"
                nameKey="section"
                cx="50%"
                cy="50%"
                outerRadius={100}
                label={(entry) => `${entry.section}: ${entry.count}`}
                labelLine={{ stroke: '#94a3b8', strokeWidth: 1 }}
              >
                {analytics.by_section.map((entry, index) => (
                  <Cell 
                    key={`cell-${index}`} 
                    fill={COLORS[entry.section as keyof typeof COLORS] || PIE_COLORS[index % PIE_COLORS.length]} 
                  />
                ))}
              </Pie>
              <Tooltip 
                contentStyle={{ 
                  backgroundColor: 'white', 
                  border: '1px solid #e5e7eb',
                  borderRadius: '8px'
                }}
              />
            </PieChart>
          </ResponsiveContainer>

          <div className="mt-6 text-center">
            <div className="text-sm text-gray-500">
              Всего документов: <span className="font-semibold text-gray-900">{analytics.total_documents}</span>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default AnalyticsSectionCharts;
