from typing import List

class Solution:
    def jobSequencing(self, deadline, profit):
        # code here
        jobs = []
        for i in range(len(deadline)):
            jobs.append([deadline[i],profit[i],i+1])
        jobs = sorted(jobs,key=lambda x:(-x[1],-x[0]))
        print(jobs)
        schedule = [0 for _ in range(len(jobs)+1)]
        result = [0,0]
        for i in range(len(jobs)):
            for j in range(jobs[i][0],0,-1):
                if schedule[j]==0:
                    schedule[j]=jobs[i][2]
                    result[0]+=1
                    result[1]+=jobs[i][1]
                    break
        return result

if __name__=="__main__":

    sol = Solution()
    deadline = [4, 1, 1, 1]
    profit = [20, 10, 40, 30]
    print("result : ",sol.jobSequencing(deadline, profit))
    