"""
Dashboard Fetcher - Silently fetch component data from the defect monitoring dashboard
"""
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException

class DashboardFetcher:
    def __init__(self):
        self.driver = None
        self.base_url = "https://defectmonitoring.dev.fyre.ibm.com/dashboard"
    
    def setup_browser(self):
        """Setup headless Chrome browser"""
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.implicitly_wait(10)
    
    def fetch_component_data(self, component_name):
        """
        Fetch all data for a specific component
        
        Args:
            component_name: Name of the component to fetch data for
            
        Returns:
            dict: Component data including all available metrics
        """
        try:
            self.setup_browser()
            
            # Navigate to dashboard
            print(f"Accessing dashboard...")
            self.driver.get(self.base_url)
            time.sleep(3)
            
            # Find and select component from dropdown
            print(f"Selecting component: {component_name}")
            component_dropdown = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "componentSelect"))
            )
            component_dropdown.click()
            time.sleep(1)
            
            # Find the specific component option
            component_option = self.driver.find_element(
                By.XPATH, 
                f"//option[contains(text(), '{component_name}')]"
            )
            component_option.click()
            time.sleep(1)
            
            # Turn off auto-refresh
            print("Turning off auto-refresh...")
            try:
                auto_refresh_toggle = self.driver.find_element(By.ID, "autoRefreshToggle")
                if auto_refresh_toggle.is_selected():
                    auto_refresh_toggle.click()
                    time.sleep(0.5)
            except NoSuchElementException:
                print("Auto-refresh toggle not found, continuing...")
            
            # Click View Dashboard button
            print("Clicking View Dashboard...")
            view_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.ID, "viewDashboardBtn"))
            )
            view_button.click()
            time.sleep(3)
            
            # Extract all data from the dashboard
            print("Extracting component data...")
            data = self._extract_dashboard_data(component_name)
            
            return data
            
        except Exception as e:
            return {
                "error": str(e),
                "component": component_name,
                "status": "failed"
            }
        finally:
            if self.driver:
                self.driver.quit()
    
    def _extract_dashboard_data(self, component_name):
        """Extract all available data from the dashboard"""
        data = {
            "component": component_name,
            "status": "success"
        }
        
        try:
            # Total defects
            total_defects = self.driver.find_element(By.ID, "totalDefects").text
            data["total_defects"] = total_defects
        except:
            data["total_defects"] = "N/A"
        
        try:
            # Untriaged defects
            untriaged = self.driver.find_element(By.ID, "untriagedDefects").text
            data["untriaged_defects"] = untriaged
        except:
            data["untriaged_defects"] = "N/A"
        
        try:
            # Aged defects
            aged = self.driver.find_element(By.ID, "agedDefects").text
            data["aged_defects"] = aged
        except:
            data["aged_defects"] = "N/A"
        
        try:
            # Duplicate defects
            duplicates = self.driver.find_element(By.ID, "duplicateDefects").text
            data["duplicate_defects"] = duplicates
        except:
            data["duplicate_defects"] = "N/A"
        
        try:
            # Recent defects
            recent = self.driver.find_element(By.ID, "recentDefects").text
            data["recent_defects"] = recent
        except:
            data["recent_defects"] = "N/A"
        
        try:
            # Triaged defects
            triaged = self.driver.find_element(By.ID, "triagedDefects").text
            data["triaged_defects"] = triaged
        except:
            data["triaged_defects"] = "N/A"
        
        try:
            # Get defect list if available
            defect_table = self.driver.find_element(By.ID, "defectTable")
            rows = defect_table.find_elements(By.TAG_NAME, "tr")
            defects = []
            for row in rows[1:]:  # Skip header
                cols = row.find_elements(By.TAG_NAME, "td")
                if len(cols) >= 3:
                    defects.append({
                        "id": cols[0].text,
                        "summary": cols[1].text,
                        "status": cols[2].text
                    })
            data["defect_list"] = defects
        except:
            data["defect_list"] = []
        
        return data


def get_component_info(component_name, info_type=None):
    """
    Get information about a component from the dashboard
    
    Args:
        component_name: Name of the component
        info_type: Specific info to retrieve (optional)
                  Options: 'total', 'untriaged', 'aged', 'duplicates', 'all'
    
    Returns:
        Formatted string with the requested information
    """
    fetcher = DashboardFetcher()
    data = fetcher.fetch_component_data(component_name)
    
    if data.get("status") == "failed":
        return f"Error fetching data for {component_name}: {data.get('error')}"
    
    # Format output based on info_type
    if info_type == 'total':
        return f"Total defects for {component_name}: {data['total_defects']}"
    elif info_type == 'untriaged':
        return f"Untriaged defects for {component_name}: {data['untriaged_defects']}"
    elif info_type == 'aged':
        return f"Aged defects for {component_name}: {data['aged_defects']}"
    elif info_type == 'duplicates':
        return f"Duplicate defects for {component_name}: {data['duplicate_defects']}"
    else:
        # Return all information
        output = f"\n=== {component_name} Dashboard ===\n"
        output += f"Total Defects: {data['total_defects']}\n"
        output += f"Untriaged: {data['untriaged_defects']}\n"
        output += f"Aged: {data['aged_defects']}\n"
        output += f"Duplicates: {data['duplicate_defects']}\n"
        output += f"Recent: {data['recent_defects']}\n"
        output += f"Triaged: {data['triaged_defects']}\n"
        
        if data.get('defect_list'):
            output += f"\nDefect List ({len(data['defect_list'])} defects):\n"
            for defect in data['defect_list'][:10]:  # Show first 10
                output += f"  - {defect['id']}: {defect['summary']}\n"
        
        return output


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python dashboard_fetcher.py <component_name> [info_type]")
        print("Info types: total, untriaged, aged, duplicates, all")
        sys.exit(1)
    
    component = sys.argv[1]
    info_type = sys.argv[2] if len(sys.argv) > 2 else 'all'
    
    result = get_component_info(component, info_type)
    print(result)

# Made with Bob
