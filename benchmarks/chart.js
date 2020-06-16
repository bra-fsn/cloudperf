// Load the Visualization API and the controls package.
google.load('visualization', '1.0', {
  'packages': ['corechart', 'controls']
});

// Set a callback to run when the Google Visualization API is loaded.
google.setOnLoadCallback(drawDashboard);

// Callback that creates and populates a data table,
// instantiates a dashboard, a range slider and a pie chart,
// passes in the data and draws it.
function drawDashboard() {
  var data = new google.visualization.DataTable();
  data.addColumn('string', 'instanceType');
  data.addColumn('number', 'benchmark_score');
  data.addColumn('number', 'vcpu');
  data.addColumn('string', 'benchmark_id');
  data.addColumn('string', 'physicalProcessor');

  getData();

  function getData() {
    $.ajax({
      url: 'https://cloudperf-data.s3-us-west-2.amazonaws.com/webperf.json',
      dataType: 'json'
    }).done(function(jsonData) {
      loadData(jsonData);
      delete jsonData;
    });
  }

  function loadData(jsonData) {
    // load json data
    $.each(jsonData, function(index, row) {
      data.addRow([
        row.instanceType,
        parseFloat(row.benchmark_score),
        parseFloat(row.vcpu),
        String(row.benchmark_id),
        row.physicalProcessor,
      ]);
    });
    data.sort({
      column: 1,
      desc: true
    });
    dashboard.draw(data);
  }

  // Create a dashboard.
  var dashboard = new google.visualization.Dashboard(
    document.getElementById('dashboard_div'));

  var instanceTypeFilter = new google.visualization.ControlWrapper({
    'controlType': 'CategoryFilter',
    'containerId': 'instanceTypeFilter_div',
    'options': {
      'filterColumnLabel': 'instanceType'
    }
  });

  var vcpuFilter = new google.visualization.ControlWrapper({
    'controlType': 'CategoryFilter',
    'containerId': 'vcpuFilter_div',
    'options': {
      'filterColumnLabel': 'vcpu',
      'ui': {
            'sortValues': true
        }
    }
  });

  var benchmarkFilter = new google.visualization.ControlWrapper({
    'controlType': 'CategoryFilter',
    'containerId': 'benchmarkFilter_div',
    'options': {
      'filterColumnLabel': 'benchmark_id',
      'ui': {
            'allowMultiple': false,
            'allowNone': false
        }
    },
    'state': {'selectedValues': ['stress-ng:crc16']}
  });

  var physicalProcessorFilter = new google.visualization.ControlWrapper({
    'controlType': 'CategoryFilter',
    'containerId': 'physicalProcessorFilter_div',
    'options': {
      'filterColumnLabel': 'physicalProcessor'
    }
  });

  // Create a pie chart, passing some options
  var chart = new google.visualization.ChartWrapper({
    'chartType': 'ColumnChart',
    'containerId': 'chart_div',
    'height': '100%',
    'width': '100%',
    'options': {
      'chartArea': {
        'bottom': 60,
        'top': '10%',
        'height': '90%',
        'width': '90%'
      },
      'height': '90%',
      'legend': {
        'position': 'top'
      },
    },
    'view': {
      'columns': [0, 1]
    }
  });

  dashboard.bind(instanceTypeFilter, chart);
  dashboard.bind(vcpuFilter, chart);
  dashboard.bind(benchmarkFilter, chart);
  dashboard.bind(physicalProcessorFilter, chart);


  // Draw the dashboard.
  dashboard.draw(data);

  $(window).resize(function() {
    dashboard.draw(data);
  });
}
