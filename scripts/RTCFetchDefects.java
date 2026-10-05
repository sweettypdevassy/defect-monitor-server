/**
 * Standalone RTC defect fetcher — uses the RTC SDK JARs from rtc-mcp-server.
 * Queries WS-CD for open build-break defects by functional area and prints
 * a JSON array to stdout. Python defect-monitor-server calls this via subprocess.
 *
 * Compile:
 *   javac -cp "/path/to/rtc-mcp-server/jars/*" RTCFetchDefects.java -d out/
 *
 * Run:
 *   java -cp "/path/to/rtc-mcp-server/jars/*:out" RTCFetchDefects <user> <pass> <functionalArea>
 */

import com.ibm.rtcutil.core.RTCRepoProjectArea;
import com.ibm.rtcutil.core.RepoUtils;
import com.ibm.rtcutil.data.CustomDataModel;
import com.ibm.team.repository.client.IItemManager;
import com.ibm.team.repository.client.ITeamRepository;
import com.ibm.team.repository.client.TeamPlatform;
import com.ibm.team.repository.common.IContributor;
import com.ibm.team.repository.common.IContributorHandle;
import com.ibm.team.workitem.client.IWorkItemClient;
import com.ibm.team.workitem.common.expression.AttributeExpression;
import com.ibm.team.workitem.common.expression.Expression;
import com.ibm.team.workitem.common.expression.SelectClause;
import com.ibm.team.workitem.common.expression.SortCriteria;
import com.ibm.team.workitem.common.expression.Statement;
import com.ibm.team.workitem.common.expression.Term;
import com.ibm.team.workitem.common.expression.Term.Operator;
import com.ibm.team.workitem.common.model.AttributeOperation;
import com.ibm.team.workitem.common.model.IWorkItem;

import java.util.ArrayList;
import java.util.List;

public class RTCFetchDefects {

    static final String REPO_URL     = "https://wasrtc.hursley.ibm.com:9443/jazz/";
    static final String PROJECT_AREA = "WS-CD";

    public static void main(String[] args) throws Exception {
        if (args.length < 3) {
            System.err.println("Usage: RTCFetchDefects <user> <pass> <functionalArea>");
            System.exit(1);
        }
        String user = args[0];
        String pass = args[1];
        String fa   = args[2];

        TeamPlatform.startup();
        try {
            ITeamRepository repo = TeamPlatform.getTeamRepositoryService()
                    .getTeamRepository(REPO_URL);
            repo.registerLoginHandler(r -> new ITeamRepository.ILoginHandler.ILoginInfo() {
                public String getUserId()   { return user; }
                public String getPassword() { return pass; }
            });
            RepoUtils.verboseLogging(false);
            repo.login(RepoUtils.getProgressMonitor());

            RTCRepoProjectArea projectArea = RepoUtils.getProjectAreaFromRepository(
                    repo, new CustomDataModel(PROJECT_AREA));
            projectArea.setDefaultCreator();

            List<IWorkItem> items = findOpenBuildBreaks(projectArea, fa);

            // Output JSON array to stdout
            StringBuilder sb = new StringBuilder("[");
            boolean first = true;
            for (IWorkItem wi : items) {
                if (!first) sb.append(",");
                first = false;
                String owner = resolveOwner(projectArea, wi.getOwner());
                String state = resolveState(
                        wi.getState2() != null ? wi.getState2().getStringIdentifier() : "");
                List<String> tags = wi.getTags2() != null ? wi.getTags2() : List.of();
                String summary = wi.getHTMLSummary() != null
                        ? escJson(wi.getHTMLSummary().toString()) : "";
                sb.append("{")
                  .append("\"id\":").append(wi.getId()).append(",")
                  .append("\"summary\":\"").append(summary).append("\",")
                  .append("\"owner\":\"").append(escJson(owner)).append("\",")
                  .append("\"state\":\"").append(escJson(state)).append("\",")
                  .append("\"tags\":").append(toJsonArray(tags))
                  .append("}");
            }
            sb.append("]");
            System.out.println(sb);

            repo.logout();
        } finally {
            TeamPlatform.shutdown();
        }
    }

    static List<IWorkItem> findOpenBuildBreaks(RTCRepoProjectArea pa, String fa) throws Exception {
        var monitor  = RepoUtils.getProgressMonitor();
        var qPA      = pa.findQueryableAttribute(IWorkItem.PROJECT_AREA_PROPERTY);
        var qType    = pa.findQueryableAttribute(IWorkItem.TYPE_PROPERTY);
        var qState   = pa.findQueryableAttribute(IWorkItem.STATE_PROPERTY);
        var relAttr  = pa.findAttribute("release");
        var qRel     = pa.findQueryableAttribute("release");
        var sevAttr  = pa.findAttribute("internalSeverity");
        var qSev     = pa.findQueryableAttribute("internalSeverity");
        var profAttr = pa.findAttribute("profileOrEdition");
        var qProf    = pa.findQueryableAttribute("profileOrEdition");
        var faAttr   = pa.findAttribute("functional_area");
        var qFa      = pa.findQueryableAttribute("functional_area");

        var stmt = new Statement(
                new SelectClause(),
                new Term(Operator.AND, new Expression[]{
                    new AttributeExpression(qPA,   AttributeOperation.EQUALS, pa.getProjectArea()),
                    new AttributeExpression(qType, AttributeOperation.EQUALS,
                            pa.findWorkItemType("defect").getIdentifier()),
                    new AttributeExpression(qRel,  AttributeOperation.EQUALS,
                            pa.findLiteralByName("Next", relAttr)),
                    new AttributeExpression(qSev,  AttributeOperation.EQUALS,
                            pa.findLiteralByName("(*) Build Break", sevAttr)),
                    new AttributeExpression(qProf, AttributeOperation.EQUALS,
                            pa.findLiteralByName("Liberty", profAttr)),
                    new AttributeExpression(qFa,   AttributeOperation.EQUALS,
                            pa.findLiteralByName(fa, faAttr)),
                    new Term(Operator.OR, new Expression[]{
                        new AttributeExpression(qState, AttributeOperation.EQUALS,
                                "commonWorkflow.state.open"),
                        new AttributeExpression(qState, AttributeOperation.EQUALS,
                                "commonWorkflow.state.inprogress"),
                        new AttributeExpression(qState, AttributeOperation.EQUALS,
                                "commonWorkflow.state.debugging"),
                        new AttributeExpression(qState, AttributeOperation.EQUALS,
                                "commonWorkflow.state.returned"),
                        new AttributeExpression(qState, AttributeOperation.EQUALS,
                                "defect_workflow.state.s1"),
                    })
                }),
                List.of(new SortCriteria(pa.findQueryableAttribute(IWorkItem.ID_PROPERTY), true)));

        IWorkItemClient wiClient = pa.getWorkItemClient();
        List<IWorkItem> result = new ArrayList<>();
        for (IWorkItem item : pa.queryWorkItems(stmt)) {
            result.add(wiClient.findWorkItemById(item.getId(), IWorkItem.FULL_PROFILE, monitor));
        }
        return result;
    }

    static String resolveOwner(RTCRepoProjectArea pa, IContributorHandle handle) {
        try {
            if (handle == null) return "Unassigned";
            IContributor c = (IContributor) pa.getItemManager()
                    .fetchCompleteItem(handle, IItemManager.DEFAULT,
                            RepoUtils.getProgressMonitor());
            String name = c.getName();
            return name != null ? name : "Unassigned";
        } catch (Exception e) {
            return "Unassigned";
        }
    }

    static String resolveState(String id) {
        if (id == null) return "";
        switch (id) {
            case "commonWorkflow.state.open":           return "Open";
            case "commonWorkflow.state.returned":       return "Returned";
            case "commonWorkflow.state.debugging":      return "Debugging";
            case "commonWorkflow.state.inprogress":     return "In Progress";
            case "defect_workflow.state.s1":            return "In Progress (GHE)";
            case "commonWorkflow.state.buildpending":   return "Pending Build";
            case "commonWorkflow.state.deliverpending": return "Pending Delivery";
            case "commonWorkflow.state.reviewpending":  return "Pending Review";
            case "commonWorkflow.state.ready":          return "Ready";
            case "defect_workflow.state.s3":            return "Ready to Verify (GHE)";
            default:                                    return id;
        }
    }

    static String escJson(String s) {
        if (s == null) return "";
        return s.replace("\\", "\\\\").replace("\"", "\\\"")
                .replace("\n", " ").replace("\r", "").replace("\t", " ");
    }

    static String toJsonArray(List<String> tags) {
        StringBuilder sb = new StringBuilder("[");
        boolean first = true;
        for (String t : tags) {
            if (!first) sb.append(",");
            first = false;
            sb.append("\"").append(escJson(t)).append("\"");
        }
        return sb.append("]").toString();
    }
}
