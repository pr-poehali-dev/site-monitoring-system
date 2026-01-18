import { useState, useRef, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import Icon from '@/components/ui/icon';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceArea } from 'recharts';

interface AnalyticsPublicationChartProps {
  analytics: {
    by_publication_date: { date: string; count: number }[];
  };
}

const AnalyticsPublicationChart = ({ analytics }: AnalyticsPublicationChartProps) => {
  const [refAreaLeft, setRefAreaLeft] = useState<string>('');
  const [refAreaRight, setRefAreaRight] = useState<string>('');
  const [chartData, setChartData] = useState<any[]>([]);
  const [left, setLeft] = useState<number>(0);
  const [right, setRight] = useState<number>(0);
  const [top, setTop] = useState<number>(0);
  const [bottom, setBottom] = useState<number>(0);
  const [hoveredLabel, setHoveredLabel] = useState<string>('');
  
  const chartContainerRef = useRef<HTMLDivElement>(null);

  const fullData = analytics?.by_publication_date || [];
  const displayData = chartData.length > 0 ? chartData : fullData;

  const getSmartTicks = () => {
    const dataLength = displayData.length;
    
    if (dataLength <= 30) {
      return displayData.map(item => item.date);
    }
    
    if (dataLength <= 90) {
      return displayData.filter((_, idx) => idx % 3 === 0).map(item => item.date);
    }
    
    if (dataLength <= 180) {
      return displayData.filter((_, idx) => idx % 7 === 0).map(item => item.date);
    }
    
    if (dataLength <= 365) {
      return displayData.filter((_, idx) => idx % 14 === 0).map(item => item.date);
    }
    
    return displayData
      .filter((item) => {
        const date = item.date.split('.')[0];
        return date === '01';
      })
      .map(item => item.date);
  };

  const formatTickLabel = (value: string) => {
    const dataLength = displayData.length;
    
    if (dataLength <= 90) {
      return value;
    }
    
    if (dataLength <= 365) {
      const [day, month, year] = value.split('.');
      return `${day}.${month}`;
    }
    
    const [, month, year] = value.split('.');
    return `${month}.${year}`;
  };

  const zoomOut = () => {
    setChartData([]);
    setLeft(0);
    setRight(0);
    setTop(0);
    setBottom(0);
    setRefAreaLeft('');
    setRefAreaRight('');
  };

  useEffect(() => {
    const container = chartContainerRef.current;
    if (!container) return;

    const handleWheelEvent = (e: WheelEvent) => {
      if (!hoveredLabel) return;
      
      e.preventDefault();
      e.stopPropagation();
      
      const delta = e.deltaY;
      if (delta === 0) return;

      const direction = delta > 0 ? 1 : -1;
      const mouseIndex = fullData.findIndex(item => item.date === hoveredLabel);
      
      if (mouseIndex === -1) return;

      const currentLeft = left || 0;
      const currentRight = right || fullData.length - 1;
      const currentRange = currentRight - currentLeft;

      if (direction < 0) {
        const minRange = 30;
        if (currentRange <= minRange) return;

        const zoomFactor = 0.8;
        const newRange = Math.max(minRange, Math.floor(currentRange * zoomFactor));
        const rangeDiff = currentRange - newRange;

        const mouseRelativePos = (mouseIndex - currentLeft) / currentRange;
        const newLeft = Math.max(0, currentLeft + Math.floor(rangeDiff * mouseRelativePos));
        const newRight = Math.min(fullData.length - 1, newLeft + newRange);

        const newData = fullData.slice(newLeft, newRight + 1);
        const counts = newData.map(item => item.count);
        
        setChartData(newData);
        setLeft(newLeft);
        setRight(newRight);
        setTop(Math.max(...counts));
        setBottom(Math.min(...counts));
      } else {
        if (currentLeft === 0 && currentRight === fullData.length - 1) return;

        const zoomFactor = 1.25;
        const newRange = Math.min(fullData.length - 1, Math.floor(currentRange * zoomFactor));
        const rangeDiff = newRange - currentRange;

        const mouseRelativePos = (mouseIndex - currentLeft) / currentRange;
        const newLeft = Math.max(0, currentLeft - Math.floor(rangeDiff * mouseRelativePos));
        const newRight = Math.min(fullData.length - 1, newLeft + newRange);

        if (newLeft === 0 && newRight === fullData.length - 1) {
          setChartData([]);
          setLeft(0);
          setRight(0);
          setTop(0);
          setBottom(0);
          setRefAreaLeft('');
          setRefAreaRight('');
          return;
        }

        const newData = fullData.slice(newLeft, newRight + 1);
        const counts = newData.map(item => item.count);
        
        setChartData(newData);
        setLeft(newLeft);
        setRight(newRight);
        setTop(Math.max(...counts));
        setBottom(Math.min(...counts));
      }
    };

    container.addEventListener('wheel', handleWheelEvent, { passive: false });
    
    return () => {
      container.removeEventListener('wheel', handleWheelEvent);
    };
  }, [hoveredLabel, fullData, left, right]);

  const handleMouseMove = (e: any) => {
    if (e && e.activeLabel) {
      setHoveredLabel(e.activeLabel);
    }
  };

  const handleMouseLeave = () => {
    setHoveredLabel('');
  };

  const zoom = () => {
    if (refAreaLeft === refAreaRight || refAreaRight === '') {
      setRefAreaLeft('');
      setRefAreaRight('');
      return;
    }

    let leftIndex = fullData.findIndex((item) => item.date === refAreaLeft);
    let rightIndex = fullData.findIndex((item) => item.date === refAreaRight);

    if (leftIndex === -1 || rightIndex === -1) return;

    if (leftIndex > rightIndex) {
      [leftIndex, rightIndex] = [rightIndex, leftIndex];
    }

    const minRange = 30;
    if (rightIndex - leftIndex < minRange) {
      alert(`Минимальный диапазон для масштабирования: ${minRange} дней`);
      setRefAreaLeft('');
      setRefAreaRight('');
      return;
    }

    const newData = fullData.slice(leftIndex, rightIndex + 1);
    const counts = newData.map((item) => item.count);
    
    setChartData(newData);
    setLeft(leftIndex);
    setRight(rightIndex);
    setRefAreaLeft('');
    setRefAreaRight('');
    setTop(Math.max(...counts));
    setBottom(Math.min(...counts));
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Динамика публикаций документов</CardTitle>
            <CardDescription>
              {chartData.length > 0 
                ? `Показано ${displayData.length} дней из ${fullData.length} (приближено)`
                : `Последние 5 лет = ${fullData.length} дней`
              }
            </CardDescription>
          </div>
          {chartData.length > 0 && (
            <Button 
              variant="outline" 
              size="sm"
              onClick={zoomOut}
            >
              <Icon name="ZoomOut" size={14} className="mr-1" />
              Сбросить zoom
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <div ref={chartContainerRef}>
          <ResponsiveContainer width="100%" height={400}>
            <LineChart 
              data={displayData}
              onMouseDown={(e: any) => e && e.activeLabel && setRefAreaLeft(e.activeLabel)}
              onMouseMove={(e: any) => {
                handleMouseMove(e);
                if (refAreaLeft && e && e.activeLabel) setRefAreaRight(e.activeLabel);
              }}
              onMouseUp={zoom}
              onMouseLeave={handleMouseLeave}
            >
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis 
              dataKey="date"
              ticks={getSmartTicks()}
              tickFormatter={formatTickLabel}
              tick={{ fontSize: 10, angle: -45, textAnchor: 'end' }}
              height={80}
            />
            <YAxis 
              tick={{ fontSize: 12 }}
            />
            <Tooltip 
              contentStyle={{ 
                backgroundColor: 'white', 
                border: '1px solid #e5e7eb',
                borderRadius: '8px'
              }}
              labelFormatter={(value) => `Дата: ${value}`}
            />
            <Line 
              type="monotone" 
              dataKey="count" 
              stroke="#f59e0b" 
              strokeWidth={displayData.length < 180 ? 2 : 1}
              dot={displayData.length < 90}
              animationDuration={300}
            />
            {refAreaLeft && refAreaRight && (
              <ReferenceArea
                x1={refAreaLeft}
                x2={refAreaRight}
                strokeOpacity={0.3}
                fill="#3b82f6"
                fillOpacity={0.3}
              />
            )}
          </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <div className="flex items-start gap-3">
              <Icon name="Info" size={18} className="text-blue-600 mt-0.5" />
              <div className="text-sm text-blue-900">
                <p className="font-medium mb-1">Анализ динамики публикаций</p>
                <p className="text-xs text-blue-700">
                  График показывает количество документов, опубликованных на сайте за каждый день (включая дни с 0 публикаций). 
                  Пики активности могут указывать на важные события или плановые публикации.
                </p>
              </div>
            </div>
          </div>
          <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
            <div className="flex items-start gap-3">
              <Icon name="MousePointer2" size={18} className="text-green-600 mt-0.5" />
              <div className="text-sm text-green-900">
                <p className="font-medium mb-1">Интерактивное масштабирование</p>
                <p className="text-xs text-green-700">
                  🖱️ <strong>Выделите область мышью</strong> для увеличения (зажмите и протяните).<br/>
                  🔍 <strong>Колёсико мыши</strong> — плавное масштабирование (вверх = zoom in, вниз = zoom out).<br/>
                  Минимальный диапазон: 30 дней.
                </p>
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default AnalyticsPublicationChart;