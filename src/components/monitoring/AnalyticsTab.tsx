import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import Icon from '@/components/ui/icon';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, LineChart, Line, PieChart, Pie, Cell } from 'recharts';

interface AnalyticsTabProps {
  analytics: {
    by_section: { section: string; count: number }[];
    by_year: { year: number; count: number }[];
    by_publication_date: { date: string; count: number }[];
    total_documents: number;
    total_files: number;
    total_size_mb: number | string;
  } | null;
}

const COLORS = {
  'Постановления': '#3b82f6',
  'Распоряжения': '#10b981', 
  'Муниципальные программы': '#f59e0b'
};

const PIE_COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'];

const AnalyticsTab = ({ analytics }: AnalyticsTabProps) => {
  console.log('AnalyticsTab render:', analytics);
  
  if (!analytics) {
    return (
      <Card>
        <CardContent className="py-12">
          <div className="text-center text-gray-500">
            <Icon name="BarChart3" size={48} className="mx-auto mb-4 opacity-50" />
            <p>Загрузка аналитики...</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  const formatSize = (mb: number | string) => {
    const mbNum = typeof mb === 'string' ? parseFloat(mb) : mb;
    if (mbNum >= 1024) return `${(mbNum / 1024).toFixed(2)} ГБ`;
    return `${mbNum.toFixed(2)} МБ`;
  };

  return (
    <div className="space-y-6">
      {/* Общая статистика */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="text-center">
              <Icon name="FileText" size={24} className="mx-auto text-blue-600 mb-2" />
              <div className="text-3xl font-bold text-gray-900">{analytics.total_documents}</div>
              <div className="text-sm text-gray-500 mt-1">Документов</div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="text-center">
              <Icon name="Files" size={24} className="mx-auto text-green-600 mb-2" />
              <div className="text-3xl font-bold text-gray-900">{analytics.total_files}</div>
              <div className="text-sm text-gray-500 mt-1">Файлов</div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="text-center">
              <Icon name="HardDrive" size={24} className="mx-auto text-orange-600 mb-2" />
              <div className="text-3xl font-bold text-gray-900">{formatSize(analytics.total_size_mb)}</div>
              <div className="text-sm text-gray-500 mt-1">Общий размер</div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="text-center">
              <Icon name="Layers" size={24} className="mx-auto text-purple-600 mb-2" />
              <div className="text-3xl font-bold text-gray-900">{analytics.by_section.length}</div>
              <div className="text-sm text-gray-500 mt-1">Разделов</div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Распределение по разделам */}
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

      {/* Распределение по годам */}
      <Card>
        <CardHeader>
          <CardTitle>Документы по годам</CardTitle>
          <CardDescription>Количество документов по годам публикации</CardDescription>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={400}>
            <BarChart data={analytics.by_year}>
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
            {analytics.by_year.map((item) => (
              <div key={item.year} className="p-3 border rounded-lg text-center hover:bg-gray-50 transition-colors">
                <div className="text-xs text-gray-500">{item.year}</div>
                <div className="text-lg font-bold text-gray-900 mt-1">{item.count}</div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Динамика публикаций */}
      <Card>
        <CardHeader>
          <CardTitle>Динамика публикаций документов</CardTitle>
          <CardDescription>Количество опубликованных документов по дням (последние 90 дней)</CardDescription>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={400}>
            <LineChart data={analytics.by_publication_date}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis 
                dataKey="date" 
                tick={{ fontSize: 11 }}
                angle={-45}
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
                labelFormatter={(value) => `Дата: ${value}`}
              />
              <Legend />
              <Line 
                type="monotone" 
                dataKey="count" 
                stroke="#f59e0b" 
                strokeWidth={2}
                dot={{ fill: '#f59e0b', r: 4 }}
                activeDot={{ r: 6 }}
                name="Документов"
              />
            </LineChart>
          </ResponsiveContainer>

          <div className="mt-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <div className="flex items-start gap-3">
              <Icon name="Info" size={18} className="text-blue-600 mt-0.5" />
              <div className="text-sm text-blue-900">
                <p className="font-medium mb-1">Анализ динамики публикаций</p>
                <p className="text-xs text-blue-700">
                  График показывает количество документов, опубликованных на сайте за каждый день в последние 90 дней. 
                  Пики активности могут указывать на важные события или плановые публикации.
                </p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default AnalyticsTab;